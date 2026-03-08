from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.core.database import user_collection
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import UserSchema

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user: UserSchema):
    """
    **[Public]** Register a new user account.

    - `role` defaults to `customer`. Set to `admin` only on the backend.
    - Password is hashed with bcrypt before storage — never stored in plain text.
    - Returns a JWT token so the user is immediately logged in after signup.
    """
    # Check if email already exists
    existing_user = await user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # Hash the password before saving
    hashed_password = get_password_hash(user.password)

    user_doc = {
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "role": user.role,
        "created_at": datetime.utcnow(),
    }

    await user_collection.insert_one(user_doc)

    # Generate and return a token so the user is logged in immediately
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}
    )

    return {
        "message": "Account created successfully",
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    **[Public]** Log in with email and password.

    Uses OAuth2 password flow (standard):
    - `username` field = your **email address**
    - `password` field = your password

    Returns a JWT `access_token` to use in the `Authorization: Bearer <token>` header.
    """
    # Find user by email (OAuth2 uses "username" field, we treat it as email)
    user = await user_collection.find_one({"email": form.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(form.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create and return the JWT token
    access_token = create_access_token(
        data={"sub": user["email"], "role": user["role"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
    }
