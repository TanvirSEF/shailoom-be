from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReviewModel(BaseModel):
    product_id: str = Field(..., description="MongoDB ObjectId of the product")
    user_email: str = Field(..., description="Email of the user who bought and reviewed the product")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    comment: str = Field(..., min_length=1, max_length=1000)
    image_url: Optional[str] = Field(None, description="Optional image uploaded to R2")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
