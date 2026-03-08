import uuid
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from app.core.database import coupon_collection, order_collection, product_collection
from app.core.email import send_admin_new_order_alert, send_order_confirmation
from app.core.security import get_current_user
from app.models.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def place_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Place an order and atomically update product inventory.

    - Validates that each product has sufficient stock.
    - Decrements stock only if available (atomic update).
    - Generates a unique tracking ID (e.g. `SHL-A1B2C3D4`).
    """
    # Step 1: Initialize server-side price calculations
    calculated_subtotal = 0.0
    max_shipping_fee = 0.0
    TAX_RATE = 0.05  # 5% VAT
    
    zone_upper = order_data.shipping_zone.upper()
    is_inside_dhaka = "INSIDE" in zone_upper

    # Step 2: Check and atomically update stock for each item
    for item in order_data.items:
        try:
            p_id = ObjectId(item.product_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid product ID: {item.product_id}")

        # Fetch product details from DB to prevent client-side spoofing
        product = await product_collection.find_one(
            {"_id": p_id}, 
            {"price": 1, "stock": 1, "name": 1, "shipping_fee_inside_dhaka": 1, "shipping_fee_outside_dhaka": 1}
        )
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item.product_id} not found")
        
        calculated_subtotal += (product["price"] * item.quantity)
        
        # Calculate max shipping fee
        item_shipping = product.get("shipping_fee_inside_dhaka", 70.0) if is_inside_dhaka else product.get("shipping_fee_outside_dhaka", 130.0)
        if item_shipping > max_shipping_fee:
            max_shipping_fee = item_shipping

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
    
    # 4a. Retrieve the Max Shipping Fee computed in Step 2
    shipping_fee = max_shipping_fee
    
    # 4b. Calculate Subtotal after Discount
    discounted_subtotal = max(0.0, calculated_subtotal - discount_amount)
    
    # 4c. Calculate Tax (VAT) on discounted goods
    tax_amount = discounted_subtotal * TAX_RATE
    
    # 4d. Final Compute
    final_total = discounted_subtotal + tax_amount + shipping_fee
    
    tracking_id = f"SHL-{uuid.uuid4().hex[:8].upper()}"

    new_order = {
        **order_data.dict(exclude={"total_amount", "shipping_fee", "tax_amount", "discount_amount"}), 
        "user_email": current_user,
        "calculated_subtotal": calculated_subtotal,
        "discount_amount": discount_amount,
        "shipping_fee": shipping_fee,
        "tax_amount": tax_amount,
        "total_amount": final_total, 
        "status": "pending",
        "payment_status": "unpaid",
        "tracking_id": tracking_id,
        "created_at": datetime.utcnow(),
    }

    await order_collection.insert_one(new_order)
    
    # Trigger Email Notifications asynchronously
    background_tasks.add_task(send_order_confirmation, current_user, new_order)
    background_tasks.add_task(send_admin_new_order_alert, new_order)

    return {
        "message": "Order placed successfully",
        "tracking_id": tracking_id,
        "subtotal": calculated_subtotal,
        "discount": discount_amount,
        "shipping_fee": shipping_fee,
        "tax_amount": tax_amount,
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
    **[Authenticated]** Retrieve the concise order history of the currently logged-in user.
    """
    cursor = order_collection.find({"user_email": current_user}, {"_id": 0, "items": 0}).sort("created_at", -1)
    orders = await cursor.to_list(length=100)
    return orders


@router.get("/detail/{tracking_id}")
async def get_my_order_detail(tracking_id: str, current_user: str = Depends(get_current_user)):
    """
    **[Authenticated]** View the full detailed breakdown of a specific order belonging to the user.
    """
    order = await order_collection.find_one({"tracking_id": tracking_id, "user_email": current_user}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or access denied")
    return order


@router.patch("/{tracking_id}/cancel")
async def cancel_my_order(tracking_id: str, current_user: str = Depends(get_current_user)):
    """
    **[Authenticated]** Allows a customer to cancel their own order ONLY IF it is still 'pending'.
    Automatically recovers the inventory stock back into the product collection.
    """
    existing_order = await order_collection.find_one({"tracking_id": tracking_id, "user_email": current_user})
    
    if not existing_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    if existing_order.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot cancel order. Current status is '{existing_order.get('status')}'. Please contact support."
        )

    # 1. Update Status
    await order_collection.update_one(
        {"_id": existing_order["_id"]},
        {"$set": {"status": "cancelled", "payment_status": "refunded"}}
    )
    
    # 2. Inventory Recovery
    for item in existing_order.get("items", []):
        try:
            p_id = ObjectId(item["product_id"])
            await product_collection.update_one(
                {"_id": p_id},
                {"$inc": {"stock": item["quantity"]}}
            )
        except Exception:
            pass # Keep going if one product ID fails (e.g., product deleted)

    return {"message": f"Order {tracking_id} has been successfully cancelled."}


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
