import uuid
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import coupon_collection, order_collection, product_collection
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
    # Step 1: Initialize server-side price calculation
    calculated_subtotal = 0.0

    # Step 2: Check and atomically update stock for each item
    for item in order_data.items:
        try:
            p_id = ObjectId(item.product_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid product ID: {item.product_id}")

        # Fetch product price from DB to prevent client-side spoofing
        product = await product_collection.find_one({"_id": p_id}, {"price": 1, "stock": 1, "name": 1})
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item.product_id} not found")
        
        calculated_subtotal += (product["price"] * item.quantity)

        # Atomic update: decrease stock ONLY IF stock >= requested quantity
        result = await product_collection.update_one(
            {"_id": p_id, "stock": {"$gte": item.quantity}},
            {"$inc": {"stock": -item.quantity}},
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{product.get('name', 'Product')}' is out of stock or has insufficient quantity.",
            )

    # Step 3: Validate and Apply Coupon (if provided)
    discount_amount = 0.0
    if order_data.coupon_code:
        coupon = await coupon_collection.find_one({"code": order_data.coupon_code.upper()})
        
        if not coupon:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coupon code")
        if not coupon.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon is no longer active")
        if coupon.get("end_date") and coupon["end_date"] < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon has expired")
        if coupon.get("usage_limit", 0) > 0 and coupon.get("used_count", 0) >= coupon["usage_limit"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon usage limit reached")

        # Calculate Discount
        if coupon["discount_type"] == "percentage":
            discount_amount = calculated_subtotal * (coupon["discount_value"] / 100)
        elif coupon["discount_type"] == "fixed":
            discount_amount = min(coupon["discount_value"], calculated_subtotal) # Don't discount below 0
        
        # Increment usage count atomically
        await coupon_collection.update_one({"_id": coupon["_id"]}, {"$inc": {"used_count": 1}})

    # Step 4: Finalize Totals & Create Order
    final_total = max(0.0, calculated_subtotal - discount_amount)
    
    tracking_id = f"SHL-{uuid.uuid4().hex[:8].upper()}"

    new_order = {
        **order_data.dict(exclude={"total_amount"}), # Discard client's total, use our secure one
        "user_email": current_user,
        "calculated_subtotal": calculated_subtotal,
        "discount_amount": discount_amount,
        "total_amount": final_total, 
        "status": "pending",
        "payment_status": "unpaid",
        "tracking_id": tracking_id,
        "created_at": datetime.utcnow(),
    }

    await order_collection.insert_one(new_order)

    return {
        "message": "Order placed successfully",
        "tracking_id": tracking_id,
        "subtotal": calculated_subtotal,
        "discount": discount_amount,
        "total_charged": final_total
    }


@router.get("/validate-coupon")
async def validate_coupon(code: str, order_value: float):
    """
    **[Public/Authenticated]** Validates a coupon code during checkout and calculates the expected discount.
    """
    coupon = await coupon_collection.find_one({"code": code.upper()})
    
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid coupon code")
    if not coupon.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon is no longer active")
    if coupon.get("end_date") and coupon["end_date"] < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon has expired")
    if coupon.get("usage_limit", 0) > 0 and coupon.get("used_count", 0) >= coupon["usage_limit"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon usage limit reached")

    discount = 0.0
    if coupon["discount_type"] == "percentage":
        discount = order_value * (coupon["discount_value"] / 100)
    elif coupon["discount_type"] == "fixed":
        discount = min(coupon["discount_value"], order_value)

    return {
        "is_valid": True,
        "code": coupon["code"],
        "discount_type": coupon["discount_type"],
        "discount_amount": discount,
        "final_price": max(0.0, order_value - discount)
    }


@router.get("/my-orders")
async def get_my_orders(current_user: str = Depends(get_current_user)):
    """
    **[Authenticated]** Retrieve the order history of the currently logged-in user.
    Returns all orders placed by the user, newest first.
    """
    # Sort by created_at descending (-1) to show newest orders first
    cursor = order_collection.find({"user_email": current_user}, {"_id": 0}).sort("created_at", -1)
    orders = await cursor.to_list(length=100) # Limit to 100 for safety
    return orders


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
