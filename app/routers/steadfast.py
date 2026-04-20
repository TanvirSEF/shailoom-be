import httpx
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.audit import log_admin_action
from app.core.database import order_collection, user_collection
from app.core.email import send_order_status_update
from app.core.logger import app_logger
from app.core.security import get_current_admin
from app.core import steadfast

router = APIRouter(prefix="/admin/steadfast", tags=["Steadfast Courier"])

# Steadfast status -> Shailoom order status mapping
STATUS_MAP = {
    "delivered": "delivered",
    "partial_delivered": "delivered",
    "cancelled": "cancelled",
}


@router.post("/orders/{tracking_id}/consignment")
async def create_steadfast_consignment(
    tracking_id: str,
    background_tasks: BackgroundTasks,
    admin_email: str = Depends(get_current_admin),
):
    """**[Admin Only]** Create a Steadfast courier consignment for an order."""
    order = await order_collection.find_one({"tracking_id": tracking_id})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.get("steadfast", {}).get("consignment_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consignment already created for this order",
        )

    # Resolve recipient name from user profile
    user = await user_collection.find_one({"email": order["user_email"]}, {"username": 1})
    recipient_name = (user.get("username") if user else None) or order["user_email"].split("@")[0]

    try:
        result = await steadfast.create_consignment(order, recipient_name)
    except httpx.HTTPStatusError as e:
        detail = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else e.response.text
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to connect to Steadfast API")

    consignment = result.get("consignment", result)

    await order_collection.update_one(
        {"tracking_id": tracking_id},
        {"$set": {
            "steadfast": {
                "consignment_id": consignment.get("consignment_id"),
                "tracking_code": consignment.get("tracking_code"),
                "status": consignment.get("status", "in_review"),
                "created_at": datetime.utcnow(),
            },
            "status": "shipped",
        }},
    )

    background_tasks.add_task(log_admin_action, admin_email, "CREATE_CONSIGNMENT", "orders", tracking_id, {"consignment_id": consignment.get("consignment_id")})
    background_tasks.add_task(send_order_status_update, order.get("user_email", ""), tracking_id, "shipped")

    return {
        "message": "Consignment created successfully",
        "tracking_id": tracking_id,
        "consignment_id": consignment.get("consignment_id"),
        "courier_tracking_code": consignment.get("tracking_code"),
        "courier_status": consignment.get("status", "in_review"),
    }


@router.get("/orders/{tracking_id}/delivery-status")
async def get_order_delivery_status(
    tracking_id: str,
    admin_email: str = Depends(get_current_admin),
):
    """**[Admin Only]** Check live Steadfast delivery status for an order."""
    order = await order_collection.find_one({"tracking_id": tracking_id})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    sf = order.get("steadfast")
    if not sf or not sf.get("consignment_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Steadfast consignment for this order")

    try:
        result = await steadfast.get_status_by_consignment_id(sf["consignment_id"])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Steadfast API error")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to connect to Steadfast API")

    delivery_status = result.get("delivery_status")

    # Auto-update local order status if Steadfast reports a terminal state
    mapped = STATUS_MAP.get(delivery_status)
    if mapped and order.get("status") != mapped:
        update = {"steadfast.status": delivery_status, "status": mapped}
        if mapped == "delivered":
            update["payment_status"] = "paid"
        await order_collection.update_one({"tracking_id": tracking_id}, {"$set": update})
        app_logger.info(f"Auto-updated order {tracking_id} to '{mapped}' from Steadfast status '{delivery_status}'")
    else:
        await order_collection.update_one({"tracking_id": tracking_id}, {"$set": {"steadfast.status": delivery_status}})

    return {"tracking_id": tracking_id, "delivery_status": delivery_status, "raw": result}


@router.get("/consignment/{consignment_id}/status")
async def get_consignment_status(
    consignment_id: str,
    admin_email: str = Depends(get_current_admin),
):
    """**[Admin Only]** Check Steadfast status by consignment ID directly."""
    try:
        result = await steadfast.get_status_by_consignment_id(consignment_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Steadfast API error")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to connect to Steadfast API")
    return result


@router.get("/balance")
async def get_steadfast_balance(admin_email: str = Depends(get_current_admin)):
    """**[Admin Only]** Check current Steadfast account balance."""
    try:
        result = await steadfast.get_balance()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Steadfast API error")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to connect to Steadfast API")
    return result


@router.post("/sync-statuses")
async def sync_delivery_statuses(
    background_tasks: BackgroundTasks,
    admin_email: str = Depends(get_current_admin),
):
    """**[Admin Only]** Bulk sync all pending Steadfast consignment statuses."""
    orders = await order_collection.find(
        {"steadfast.consignment_id": {"$exists": True}, "status": {"$nin": ["delivered", "cancelled"]}},
        {"tracking_id": 1, "steadfast": 1},
    ).to_list(500)

    synced = 0
    errors = 0

    for order in orders:
        try:
            result = await steadfast.get_status_by_consignment_id(order["steadfast"]["consignment_id"])
            delivery_status = result.get("delivery_status")

            update = {"steadfast.status": delivery_status}
            mapped = STATUS_MAP.get(delivery_status)
            if mapped:
                update["status"] = mapped
                if mapped == "delivered":
                    update["payment_status"] = "paid"

            await order_collection.update_one({"tracking_id": order["tracking_id"]}, {"$set": update})
            synced += 1
        except Exception as e:
            app_logger.error(f"Sync failed for order {order['tracking_id']}: {e}")
            errors += 1

    background_tasks.add_task(log_admin_action, admin_email, "SYNC_STEADFAST", "orders", "bulk", {"synced": synced, "errors": errors})

    return {"synced": synced, "errors": errors, "total_checked": len(orders)}
