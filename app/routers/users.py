from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import product_collection, user_collection
from app.core.security import get_current_user
from app.models.user import UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_my_profile(current_user_email: str = Depends(get_current_user)):
    """
    **[Authenticated]** Retrieve the profile of the currently logged-in user.
    Password hash and internal MongoDB `_id` are excluded for security.
    """
    user = await user_collection.find_one({"email": current_user_email}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    
    return user


@router.put("/me")
async def update_my_profile(
    update_data: UserUpdate,
    current_user_email: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Update the profile of the currently logged-in user.
    Only `username`, `phone_number`, and `address` can be updated.
    """
    # Remove fields that were not provided in the request
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for update"
        )

    result = await user_collection.update_one(
        {"email": current_user_email},
        {"$set": update_dict}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    if result.modified_count == 0:
        return {"message": "Profile data is already up to date"}

    return {"message": "Profile updated successfully"}


# ==========================================
# WISHLIST MANAGEMENT
# ==========================================

@router.post("/me/wishlist/{product_id}")
async def add_to_wishlist(
    product_id: str,
    current_user_email: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Add a product to the user's wishlist.
    """
    try:
        p_id = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")

    # Check if product exists
    product = await product_collection.find_one({"_id": p_id, "is_active": True})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Add to wishlist (using $addToSet to prevent duplicates)
    await user_collection.update_one(
        {"email": current_user_email},
        {"$addToSet": {"wishlist": product_id}}
    )

    return {"message": "Product added to wishlist"}


@router.delete("/me/wishlist/{product_id}")
async def remove_from_wishlist(
    product_id: str,
    current_user_email: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Remove a product from the user's wishlist.
    """
    # Remove from wishlist (using $pull)
    result = await user_collection.update_one(
        {"email": current_user_email},
        {"$pull": {"wishlist": product_id}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in wishlist")

    return {"message": "Product removed from wishlist"}


@router.get("/me/wishlist")
async def get_my_wishlist(current_user_email: str = Depends(get_current_user)):
    """
    **[Authenticated]** View all products saved in the user's wishlist.
    """
    # 1. Fetch user to get wishlist IDs
    user = await user_collection.find_one({"email": current_user_email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    wishlist_ids = user.get("wishlist", [])
    if not wishlist_ids:
        return []

    # 2. Convert string IDs to ObjectIds
    object_ids = []
    for uid in wishlist_ids:
        try:
            object_ids.append(ObjectId(uid))
        except Exception:
            continue

    # 3. Fetch products from the product collection
    products = await product_collection.find({"_id": {"$in": object_ids}}).to_list(None)
    
    # 4. Format for response
    for product in products:
        product["_id"] = str(product["_id"])

    return products
