from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CouponModel(BaseModel):
    """Schema for promotional discount codes."""
    code: str = Field(..., min_length=3, max_length=20, description="Unique promo code e.g. EID50")
    discount_type: str = Field(..., description="'percentage' or 'fixed'")
    discount_value: float = Field(..., gt=0, description="Percentage (e.g. 10) or Fixed Amount (e.g. 500)")
    start_date: datetime = Field(default_factory=datetime.utcnow)
    end_date: datetime = Field(..., description="Expiration date of the coupon")
    usage_limit: int = Field(default=0, ge=0, description="0 means unlimited usage")
    used_count: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
