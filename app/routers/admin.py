from datetime import datetime, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks

from app.core.database import audit_collection, coupon_collection, order_collection, product_collection, user_collection
from app.core.audit import log_admin_action
from app.core.email import send_order_status_update
from app.core.logger import app_logger
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


@router.patch("/orders/{tracking_id}")
async def update_order_status(
    tracking_id: str,
    order_status: str,
    background_tasks: BackgroundTasks,
    payment_status: Optional[str] = None,
    admin_email: str = Depends(get_current_admin),
):
    """
    **[Admin Only]** Update the status of an order.
    - `order_status`: e.g. `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`
    - `payment_status` *(optional)*: `unpaid` or `paid`
    """
    # 1. Retrieve the existing order to compare statuses
    existing_order = await order_collection.find_one({"tracking_id": tracking_id})
    if not existing_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
        
    # 2. Setup the update payload
    update_data = {"status": order_status}
    if payment_status:
        update_data["payment_status"] = payment_status

    # 3. Inventory Recovery Logic (Only trigger if transitioning INTO 'cancelled')
    if existing_order.get("status") != "cancelled" and order_status == "cancelled":
        app_logger.info(f"Order {tracking_id} cancelled. Recovering inventory...")
        for item in existing_order.get("items", []):
            try:
                p_id = ObjectId(item["product_id"])
                await product_collection.update_one(
                    {"_id": p_id},
                    {"$inc": {"stock": item["quantity"]}}
                )
            except Exception as e:
                app_logger.error(f"Failed to recover stock for {item.get('product_id')} on order {tracking_id}: {e}")

    # 4. Finalize Status Update
    await order_collection.update_one(
        {"tracking_id": tracking_id},
        {"$set": update_data},
    )
    
    # 5. Notify the customer
    background_tasks.add_task(send_order_status_update, existing_order.get("user_email", ""), tracking_id, order_status)

    # 6. Audit Trail
    background_tasks.add_task(log_admin_action, admin_email, "ORDER_UPDATE", "orders", tracking_id, {"new_status": order_status})

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


@router.get("/analytics/top-customers", dependencies=[Depends(get_current_admin)])
async def get_top_customers():
    """
    **[Admin Only]** Retrieve the top 10 VIP customers based on total amount definitively spent.
    """
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {
            "$group": {
                "_id": "$user_email",
                "total_spent": {"$sum": "$total_amount"},
                "total_orders": {"$sum": 1}
            }
        },
        {"$sort": {"total_spent": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "email": "$_id",
                "total_spent": 1,
                "total_orders": 1
            }
        }
    ]
    top_customers = await order_collection.aggregate(pipeline).to_list(10)
    return top_customers


@router.get("/analytics/revenue-chart", dependencies=[Depends(get_current_admin)])
async def get_revenue_chart(days: int = Query(30, ge=7, le=365)):
    """
    **[Admin Only]** Generates timeseries revenue points for frontend charting libraries (like Recharts) over the last X days.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "status": {"$ne": "cancelled"},
            "created_at": {"$gte": start_date}
        }},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "revenue": {"$sum": "$total_amount"},
                "orders": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "revenue": 1,
                "orders": 1
            }
        }
    ]
    
    chart_data = await order_collection.aggregate(pipeline).to_list(days)
    return chart_data


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


@router.get("/audit-logs", dependencies=[Depends(get_current_admin)])
async def get_audit_logs(limit: int = 50):
    """
    **[Admin Only]** Retrieve internal admin action logs (e.g., role changes, order edits).
    """
    logs = await audit_collection.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs


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

    await log_admin_action(current_admin, "CHANGE_ROLE", "users", email, {"new_role": new_role})

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


@router.delete("/coupons/{code}")
async def deactivate_coupon(code: str, admin_email: str = Depends(get_current_admin)):
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

    await log_admin_action(admin_email, "DEACTIVATE_COUPON", "coupons", code.upper())

    return {"message": f"Coupon {code.upper()} has been deactivated"}
