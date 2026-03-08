from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import order_collection
from app.core.security import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/orders", dependencies=[Depends(get_current_admin)])
async def get_all_orders():
    """
    **[Admin Only]** Retrieve all orders sorted by most recent first.
    Ideal for the admin dashboard.
    """
    orders = await order_collection.find().sort("created_at", -1).to_list(100)
    for order in orders:
        order["_id"] = str(order["_id"])
    return orders


@router.patch("/orders/{tracking_id}", dependencies=[Depends(get_current_admin)])
async def update_order_status(
    tracking_id: str,
    order_status: str,
    payment_status: Optional[str] = None,
):
    """
    **[Admin Only]** Update the status of an order.
    - `order_status`: e.g. `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`
    - `payment_status` *(optional)*: `unpaid` or `paid`
    """
    update_data = {"status": order_status}
    if payment_status:
        update_data["payment_status"] = payment_status

    result = await order_collection.update_one(
        {"tracking_id": tracking_id},
        {"$set": update_data},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or no changes were made",
        )

    return {"message": f"Order {tracking_id} updated to '{order_status}'"}
