from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import coupon_collection, order_collection, product_collection, user_collection
from app.core.security import get_current_admin
from app.models.coupon import CouponModel

router = APIRouter(prefix="/admin", tags=["Admin"])

# ==========================================
# 1. ORDER MANAGEMENT
# ==========================================

@router.get("/orders", dependencies=[Depends(get_current_admin)])
async def get_all_orders():
    """
    **[Admin Only]** Retrieve all orders sorted by most recent first.
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


# ==========================================
# 2. ANALYTICS & DASHBOARD
# ==========================================

@router.get("/analytics/sales", dependencies=[Depends(get_current_admin)])
async def get_sales_analytics():
    """
    **[Admin Only]** View sales revenue and order counts.
    Returns today's sales, this month's sales, and total all-time sales.
    Ignores 'cancelled' orders.
    """
    now = datetime.utcnow()
    start_of_today = datetime(now.year, now.month, now.day)
    start_of_month = datetime(now.year, now.month, 1)

    # Reusable aggregation pipeline base
    def build_pipeline(start_date=None):
        match_stage = {"$match": {"status": {"$ne": "cancelled"}}}
        if start_date:
            match_stage["$match"]["created_at"] = {"$gte": start_date}

        return [
            match_stage,
            {
                "$group": {
                    "_id": None,
                    "total_revenue": {"$sum": "$total_amount"},
                    "total_orders": {"$sum": 1}
                }
            }
        ]

    # Calculate metrics concurrently (or sequentially for simplicity)
    today_res = await order_collection.aggregate(build_pipeline(start_of_today)).to_list(1)
    month_res = await order_collection.aggregate(build_pipeline(start_of_month)).to_list(1)
    total_res = await order_collection.aggregate(build_pipeline()).to_list(1)

    # Extract values (default to 0 if no orders)
    def extract_stats(res_list):
        return res_list[0] if res_list else {"total_revenue": 0, "total_orders": 0}

    return {
        "today": {"revenue": extract_stats(today_res)["total_revenue"], "orders": extract_stats(today_res)["total_orders"]},
        "this_month": {"revenue": extract_stats(month_res)["total_revenue"], "orders": extract_stats(month_res)["total_orders"]},
        "all_time": {"revenue": extract_stats(total_res)["total_revenue"], "orders": extract_stats(total_res)["total_orders"]}
    }


@router.get("/analytics/low-stock", dependencies=[Depends(get_current_admin)])
async def get_low_stock_alerts(threshold: int = Query(10, ge=1)):
    """
    **[Admin Only]** Retrieve products that are running out of stock.
    Defaults to returning products with strictly less than 10 stock remaining.
    """
    low_stock_items = await product_collection.find(
        {"stock": {"$lt": threshold}},
        {"name": 1, "stock": 1, "category": 1, "price": 1} # Only return essential fields
    ).to_list(100)
    
    for item in low_stock_items:
        item["_id"] = str(item["_id"])
        
    return {
        "alert_count": len(low_stock_items),
        "items": low_stock_items
    }


# ==========================================
# 3. USER MANAGEMENT
# ==========================================

@router.get("/users", dependencies=[Depends(get_current_admin)])
async def get_all_users():
    """
    **[Admin Only]** Retrieve a list of all registered users.
    Passwords and internal IDs are hidden.
    """
    users = await user_collection.find({}, {"_id": 0, "password": 0}).sort("created_at", -1).to_list(100)
    return users


@router.patch("/users/{email}/role")
async def update_user_role(
    email: str,
    new_role: str = Query(..., pattern="^(customer|admin)$"),
    current_admin: str = Depends(get_current_admin)
):
    """
    **[Admin Only]** Promote a customer to 'admin' or demote to 'customer'.
    """
    if email == current_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role. Ask another admin to do it."
        )

    result = await user_collection.update_one(
        {"email": email},
        {"$set": {"role": new_role}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": f"User {email} is now a(n) {new_role}"}


# ==========================================
# 4. COUPON & DISCOUNT MANAGEMENT
# ==========================================

@router.post("/coupons", status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
async def create_coupon(coupon: CouponModel):
    """
    **[Admin Only]** Create a new discount coupon.
    Requires code, discount_type ('percentage' or 'fixed'), discount_value, and end_date.
    """
    # Force code to uppercase for consistency
    coupon.code = coupon.code.upper()
    
    # Check if a coupon with this code already exists
    existing = await coupon_collection.find_one({"code": coupon.code})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon code already exists")
    
    await coupon_collection.insert_one(coupon.dict())
    return {"message": f"Coupon {coupon.code} created successfully"}


@router.get("/coupons", dependencies=[Depends(get_current_admin)])
async def get_all_coupons():
    """
    **[Admin Only]** View all promotional coupons.
    """
    coupons = await coupon_collection.find().sort("created_at", -1).to_list(100)
    for c in coupons:
        c["_id"] = str(c["_id"])
    return coupons


@router.delete("/coupons/{code}", dependencies=[Depends(get_current_admin)])
async def deactivate_coupon(code: str):
    """
    **[Admin Only]** Deactivate a coupon (prevents it from being used).
    Does not delete the record to preserve order history integrity.
    """
    result = await coupon_collection.update_one(
        {"code": code.upper()},
        {"$set": {"is_active": False}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    return {"message": f"Coupon {code.upper()} has been deactivated"}
