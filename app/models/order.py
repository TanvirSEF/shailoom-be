import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    """A single line item within an order."""
    product_id: str
    name: str
    quantity: int
    price: float
    size: str
    color: str


class OrderCreate(BaseModel):
    """Schema for creating a new order (customer-facing input)."""
    items: List[OrderItem]
    total_amount: float
    shipping_address: str
    phone_number: str
    payment_method: str = Field(default="COD", example="COD or Online")
    coupon_code: Optional[str] = Field(None, description="Optional applied promo code")
    discount_amount: float = Field(default=0.0, ge=0.0, description="Calculated discount amount")


class OrderResponse(OrderCreate):
    """Full order record including system-generated fields."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_email: str
    status: str = "pending"           # pending | confirmed | shipped | delivered | cancelled
    payment_status: str = "unpaid"    # unpaid | paid
    tracking_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
