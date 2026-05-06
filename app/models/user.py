import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AddressSchema(BaseModel):
    """A saved shipping address."""
    id: str = Field(default_factory=lambda: f"addr_{uuid.uuid4().hex[:8]}")
    label: str = Field(default="Home", description="Home, Office, etc.")
    full_name: str = Field(..., min_length=2)
    phone_number: str = Field(..., min_length=11)
    address: str = Field(..., min_length=5, description="House, Road, Area")
    city: str = Field(..., min_length=2, description="dhaka, chittagong, sylhet, etc.")
    is_default: bool = Field(default=False)


class UserSchema(BaseModel):
    """Schema for creating a new user (registration)."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., example="user@shailoom.com")
    password: str = Field(..., min_length=6)
    role: str = Field(default="customer", description="'customer' or 'admin'")
    phone_number: str = Field(..., example="+8801700000000")
    addresses: List[AddressSchema] = Field(default=[], description="Saved shipping addresses")
    wishlist: List[str] = Field(default=[], description="List of saved product ObjectIds")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserUpdate(BaseModel):
    """Schema for updating an existing user's profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    phone_number: Optional[str] = Field(None, example="+8801700000000")


class UserLogin(BaseModel):
    """Schema for user login credentials."""
    email: str
    password: str
