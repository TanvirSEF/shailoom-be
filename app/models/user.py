from datetime import datetime

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    """Schema for creating a new user (registration)."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., example="user@shailoom.com")
    password: str = Field(..., min_length=6)
    role: str = Field(default="customer", description="'customer' or 'admin'")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserLogin(BaseModel):
    """Schema for user login credentials."""
    email: str
    password: str
