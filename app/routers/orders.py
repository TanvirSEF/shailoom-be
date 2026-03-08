import uuid
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import order_collection, product_collection
from app.core.security import get_current_user
from app.models.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def place_order(
    order_data: OrderCreate,
    current_user: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Place an order and atomically update product inventory.

    - Validates that each product has sufficient stock.
    - Decrements stock only if available (atomic update).
    - Generates a unique tracking ID (e.g. `SHL-A1B2C3D4`).
    """
    # Step 1: Check and atomically update stock for each item
    for item in order_data.items:
        # Convert string ID to MongoDB ObjectId
        try:
            p_id = ObjectId(item.product_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid product ID: {item.product_id}",
            )

        # Atomic update: decrease stock ONLY IF stock >= requested quantity
        result = await product_collection.update_one(
            {
                "_id": p_id,
                "stock": {"$gte": item.quantity},  # Guard: enough stock?
            },
            {
                "$inc": {"stock": -item.quantity},  # Subtract atomically
            },
        )

        # modified_count == 0 means product not found OR stock insufficient
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{item.name}' is out of stock or has insufficient quantity.",
            )

    # Step 2: All stock checks passed — create the order document
    tracking_id = f"SHL-{uuid.uuid4().hex[:8].upper()}"

    new_order = {
        **order_data.dict(),
        "user_email": current_user,
        "status": "pending",
        "payment_status": "unpaid",
        "tracking_id": tracking_id,
        "created_at": datetime.utcnow(),
    }

    await order_collection.insert_one(new_order)

    return {
        "message": "Order confirmed and stock updated",
        "tracking_id": tracking_id,
    }


@router.get("/track/{tracking_id}")
async def track_order(tracking_id: str):
    """
    **[Public]** Track an order by its unique tracking ID.
    Returns the full order status without exposing internal MongoDB IDs.
    """
    order = await order_collection.find_one({"tracking_id": tracking_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
