from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ProductModel(BaseModel):
    # Basic Information
    name: str = Field(..., example="Vintage Denim Jacket")
    description: str = Field(..., example="A premium quality denim jacket for men.")
    price: float = Field(..., gt=0, example=2500.0)
    category: str = Field(..., example="Men's Wear")

    # Shipping Fees
    shipping_fee_inside_dhaka: float = Field(default=70.0, ge=0.0, description="Delivery charge inside Dhaka")
    shipping_fee_outside_dhaka: float = Field(default=130.0, ge=0.0, description="Delivery charge outside Dhaka")

    # Clothing Specifics
    sizes: List[str] = Field(default=["S", "M", "L", "XL"])
    colors: List[str] = Field(default=["Blue", "Black"])

    # Inventory & Media
    stock: int = Field(default=0, ge=0)
    images: List[str] = Field(default=[], description="List of image URLs")

    # Ratings & Metadata
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    review_count: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
