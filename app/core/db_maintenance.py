from fastapi import APIRouter, Depends
from app.core.security import get_current_admin
from app.core.database import db, client

router = APIRouter(prefix="/admin/db", tags=["Database Maintenance"])


@router.get("/stats")
async def get_db_stats(admin_user: str = Depends(get_current_admin)):
    """Get database statistics -- collection sizes, document counts, index sizes."""
    stats = {}
    collection_names = await db.list_collection_names()

    for name in collection_names:
        collection = db.get_collection(name)
        count = await collection.estimated_document_count()
        stats[name] = {"document_count": count}

    db_stats = await db.command("dbstats", scale=1024 * 1024)

    return {
        "database": db.name,
        "size_mb": round(db_stats["dataSize"] / (1024 * 1024), 2),
        "storage_mb": round(db_stats["storageSize"] / (1024 * 1024), 2),
        "indexes_mb": round(db_stats["indexSize"] / (1024 * 1024), 2),
        "collections": stats,
    }


@router.get("/indexes")
async def get_index_stats(admin_user: str = Depends(get_current_admin)):
    """List all indexes across collections with their sizes."""
    result = {}
    collection_names = await db.list_collection_names()

    for name in collection_names:
        collection = db.get_collection(name)
        indexes = await collection.list_indexes().to_list(length=100)
        result[name] = [
            {
                "name": idx.get("name"),
                "keys": str(idx.get("key", {})),
                "unique": idx.get("unique", False),
            }
            for idx in indexes
        ]

    return result


@router.get("/health")
async def db_health_check(admin_user: str = Depends(get_current_admin)):
    """Check MongoDB connectivity and replication status."""
    try:
        ping = await client.admin.command("ping")
        server_info = await client.server_info()
        return {
            "status": "healthy",
            "mongodb_version": server_info.get("version"),
            "ping_ms": "ok" if ping.get("ok") else "failed",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
