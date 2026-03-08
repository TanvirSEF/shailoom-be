from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    """Schema for creating a new user (registration)."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., example="user@shailoom.com")
    password: str = Field(..., min_length=6)
    role: str = Field(default="customer", description="'customer' or 'admin'")
    phone_number: Optional[str] = Field(None, example="+8801700000000")
    address: Optional[str] = Field(None, example="123 Main St, Dhaka, Bangladesh")
    wishlist: List[str] = Field(default=[], description="List of saved product ObjectIds")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserUpdate(BaseModel):
    """Schema for updating an existing user's profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    phone_number: Optional[str] = Field(None, example="+8801700000000")
    address: Optional[str] = Field(None, example="123 Main St, Dhaka, Bangladesh")


class UserLogin(BaseModel):
    """Schema for user login credentials."""
    email: str
    password: str
