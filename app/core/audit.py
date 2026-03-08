from datetime import datetime
from app.core.database import audit_collection

async def log_admin_action(admin_email: str, action: str, target_collection: str, target_id: str, details: dict = None):
    """
    Asynchronously record an admin action into the audit_collection for compliance and security monitoring.
    """
    audit_doc = {
        "admin_email": admin_email,
        "action": action, 
        "target_collection": target_collection,
        "target_id": target_id,
        "details": details or {},
        "timestamp": datetime.utcnow()
    }
    await audit_collection.insert_one(audit_doc)
