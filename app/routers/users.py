from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import product_collection, user_collection
from app.core.security import get_current_user
from app.models.user import AddressSchema, UserUpdate

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
# ADDRESS BOOK
# ==========================================

@router.get("/me/addresses")
async def get_addresses(current_user_email: str = Depends(get_current_user)):
    """**[Authenticated]** Get all saved addresses for the current user."""
    user = await user_collection.find_one({"email": current_user_email}, {"addresses": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user.get("addresses", [])


@router.post("/me/addresses", status_code=status.HTTP_201_CREATED)
async def add_address(
    address: AddressSchema,
    current_user_email: str = Depends(get_current_user),
):
    """**[Authenticated]** Add a new saved address (max 5 per user)."""
    user = await user_collection.find_one({"email": current_user_email}, {"addresses": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    current_addresses = user.get("addresses", [])
    if len(current_addresses) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 addresses allowed. Delete one to add a new address."
        )

    # If this is the first address or marked as default, clear others' default
    if address.is_default or len(current_addresses) == 0:
        if current_addresses:
            await user_collection.update_one(
                {"email": current_user_email},
                {"$set": {"addresses.$[].is_default": False}}
            )
        address.is_default = True

    await user_collection.update_one(
        {"email": current_user_email},
        {"$push": {"addresses": address.dict()}}
    )

    return {"message": "Address added successfully", "address_id": address.id}


@router.patch("/me/addresses/{address_id}")
async def set_default_address(
    address_id: str,
    current_user_email: str = Depends(get_current_user),
):
    """**[Authenticated]** Set an address as the default."""
    user = await user_collection.find_one({"email": current_user_email}, {"addresses": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    addresses = user.get("addresses", [])
    found = any(a.get("id") == address_id for a in addresses)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    # Clear all defaults, then set the target
    await user_collection.update_one(
        {"email": current_user_email},
        {"$set": {"addresses.$[].is_default": False}}
    )
    await user_collection.update_one(
        {"email": current_user_email, "addresses.id": address_id},
        {"$set": {"addresses.$.is_default": True}}
    )

    return {"message": "Default address updated"}


@router.delete("/me/addresses/{address_id}")
async def delete_address(
    address_id: str,
    current_user_email: str = Depends(get_current_user),
):
    """**[Authenticated]** Delete a saved address."""
    user = await user_collection.find_one({"email": current_user_email}, {"addresses": 1})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    addresses = user.get("addresses", [])
    target = next((a for a in addresses if a.get("id") == address_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    was_default = target.get("is_default", False)

    # Pull the address
    await user_collection.update_one(
        {"email": current_user_email},
        {"$pull": {"addresses": {"id": address_id}}}
    )

    # If deleted was default, set first remaining as default
    if was_default:
        remaining = [a for a in addresses if a.get("id") != address_id]
        if remaining:
            first_id = remaining[0].get("id")
            await user_collection.update_one(
                {"email": current_user_email, "addresses.id": first_id},
                {"$set": {"addresses.$.is_default": True}}
            )

    return {"message": "Address deleted successfully"}


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
