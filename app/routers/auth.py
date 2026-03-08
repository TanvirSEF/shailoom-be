import secrets
from datetime import datetime, timedelta

import resend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import settings
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


# ==========================================
# FORGOT & RESET PASSWORD
# ==========================================

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    token: str
    new_password: str

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """
    **[Public]** Generate a secure password reset token and send an email via Resend.
    - Prevents email enumeration by standardizing the success response.
    - Token expires in 1 hour.
    """
    user = await user_collection.find_one({"email": req.email})
    
    # Generic success message to prevent enumeration attacks
    success_message = {"message": "If that email is registered, we have sent a password reset link."}
    
    if not user:
        return success_message

    # Generate cryptographically secure token
    token = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(hours=1)

    # Save token and expiry into the user's document
    await user_collection.update_one(
        {"email": req.email},
        {"$set": {"reset_token": token, "reset_token_expiry": expiry}}
    )

    # Prepare reset link (ensure this matches your frontend domain eventually)
    reset_link = f"https://shailoom.com/reset-password?token={token}&email={req.email}"

    # Send Email via Resend
    try:
        resend.api_key = settings.resend_api_key
        params: resend.Emails.SendParams = {
            "from": "Shailoom Support <onboarding@resend.dev>",
            "to": [req.email],
            "subject": "Reset Your Shailoom Password",
            "html": f"<p>Hello,</p><p>We received a request to reset your password. Click the link below to set a new password:</p><p><a href='{reset_link}'><strong>Reset Password</strong></a></p><p>This link will expire in 1 hour.</p>"
        }
        resend.Emails.send(params)
    except Exception as e:
        print(f"Failed to send reset email to {req.email}: {e}")
        # Not failing the request if email fails to maintain security obscurity
        pass

    return success_message


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """
    **[Public]** Reset a user's password using the token sent to their email.
    - Deletes the token after successful use to prevent replay attacks.
    """
    user = await user_collection.find_one({"email": req.email})
    
    if not user or not user.get("reset_token") or user.get("reset_token") != req.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )

    # Check expiration date
    if datetime.utcnow() > user.get("reset_token_expiry", datetime.min):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired."
        )

    # Hash the new password
    hashed_password = get_password_hash(req.new_password)
    
    # Intelligently update the password and invalidate the tokens
    await user_collection.update_one(
        {"email": req.email},
        {
            "$set": {"password": hashed_password},
            "$unset": {"reset_token": "", "reset_token_expiry": ""}
        }
    )

    return {"message": "Password has been reset successfully. You can now log in."}
