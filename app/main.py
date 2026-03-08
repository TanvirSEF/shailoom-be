from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import client
from app.routers import admin, orders, products


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""

    app = FastAPI(
        title=settings.app_name,
        description="Backend API for the Shailoom clothing brand.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Database Lifecycle Events ---
    @app.on_event("startup")
    async def startup_db_client():
        try:
            await client.admin.command("ping")
            print("Connected to MongoDB successfully!")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")

    @app.on_event("shutdown")
    async def shutdown_db_client():
        client.close()
        print("MongoDB connection closed.")

    # --- Health Check ---
    @app.get("/", tags=["Health"])
    async def root():
        """Health check endpoint."""
        return {"message": f"{settings.app_name} is operational", "status": "online"}

    # --- Routers ---
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(admin.router)

    return app


app = create_app()
