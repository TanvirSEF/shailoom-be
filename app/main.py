from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database import client, db
from app.core.logger import app_logger
from app.core.db_schema import COLLECTION_VALIDATORS, INDEX_DEFINITIONS
from app.routers import admin, auth, orders, products, steadfast, users
from app.core.db_maintenance import router as db_maintenance_router

# Define the Global Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""

    app = FastAPI(
        title=settings.app_name,
        description="Backend API for the Shailoom clothing brand.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- Middleware & State ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # --- Database Lifecycle Events ---
    @app.on_event("startup")
    async def startup_db_client():
        try:
            await client.admin.command("ping")
            app_logger.info("Connected to MongoDB successfully!")

            # --- Apply Schema Validation ---
            for collection_name, validator in COLLECTION_VALIDATORS.items():
                try:
                    await db.command({
                        "collMod": collection_name,
                        "validator": validator,
                        "validationLevel": "moderate",
                        "validationAction": "warn",
                    })
                    app_logger.info(f"Schema validation applied: {collection_name}")
                except Exception as e:
                    error_msg = str(e)
                    if "namespace does not exist" in error_msg.lower():
                        await db.create_collection(
                            collection_name,
                            validator=validator,
                            validationLevel="moderate",
                            validationAction="warn",
                        )
                        app_logger.info(f"Collection created with validation: {collection_name}")
                    else:
                        app_logger.warning(f"Schema validation skipped for {collection_name}: {e}")

            # --- Create Indexes ---
            for collection_name, index_spec, unique, index_name in INDEX_DEFINITIONS:
                try:
                    collection = db.get_collection(collection_name)
                    await collection.create_index(
                        index_spec,
                        unique=unique,
                        name=index_name,
                        background=True,
                    )
                except Exception as e:
                    app_logger.warning(f"Index {index_name} skipped: {e}")

            app_logger.info("MongoDB schema validation & indexes verified!")

        except Exception as e:
            app_logger.error(f"Failed to connect to MongoDB: {e}")

    @app.on_event("shutdown")
    async def shutdown_db_client():
        from app.core.steadfast import close_client as close_steadfast
        await close_steadfast()
        client.close()
        app_logger.info("MongoDB connection closed.")

    # --- Global Exception Handler (ensures CORS headers are present on 500s) ---
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        app_logger.error(f"Unhandled exception: {exc}", exc_info=True)
        response = JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )
        # Ensure CORS headers are present even on 500 errors
        request_origin = request.headers.get("origin", "")
        if request_origin in settings.allowed_origins.split(","):
            response.headers["Access-Control-Allow-Origin"] = request_origin
        return response

    # --- Health Check ---
    @app.get("/", tags=["Health"])
    async def root():
        """Health check endpoint."""
        return {"message": f"{settings.app_name} is operational", "status": "online"}
        
    # --- Dynamic SEO Sitemap ---
    @app.get("/sitemap.xml", tags=["SEO"])
    async def get_sitemap():
        """
        Generates a dynamic XML sitemap of all active products for search engine crawlers.
        """
        from app.core.database import product_collection
        
        # Base URL of the frontend (could be moved to env vars later)
        base_url = "https://shailoom.com"
        
        # Start XML
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        # Add static pages
        static_pages = ["", "/products", "/about", "/contact"]
        for page in static_pages:
            xml_content += f"  <url>\n    <loc>{base_url}{page}</loc>\n    <changefreq>daily</changefreq>\n    <priority>{1.0 if page == '' else 0.8}</priority>\n  </url>\n"

        # Add dynamic product pages
        cursor = product_collection.find({"is_active": True}, {"_id": 1, "updated_at": 1})
        products = await cursor.to_list(length=None)
        
        for product in products:
            p_id = str(product["_id"])
            # Format date to YYYY-MM-DD (fallback to UTC now if missing)
            lastmod = product.get("updated_at")
            if lastmod:
                lastmod_str = lastmod.strftime("%Y-%m-%d")
            else:
                from datetime import datetime
                lastmod_str = datetime.utcnow().strftime("%Y-%m-%d")

            xml_content += f"  <url>\n    <loc>{base_url}/products/{p_id}</loc>\n    <lastmod>{lastmod_str}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>\n"
            
        # Close XML
        xml_content += '</urlset>'
        
        return Response(content=xml_content, media_type="application/xml")

    # --- Routers ---
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(admin.router)
    app.include_router(steadfast.router)
    app.include_router(db_maintenance_router)

    return app


app = create_app()
