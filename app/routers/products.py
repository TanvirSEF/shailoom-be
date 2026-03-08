import json
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.core.database import order_collection, product_collection, review_collection
from app.core.s3 import upload_image_to_r2
from app.core.security import get_current_admin, get_current_user
from app.models.product import ProductModel
from app.models.review import ReviewModel

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    stock: int = Form(...),
    sizes: str = Form(..., examples=['["S", "M", "L", "XL"]']),
    colors: str = Form(..., examples=['["Red", "Blue"]']),
    image_files: List[UploadFile] = File(...),
    admin_user: str = Depends(get_current_admin),
):
    """
    **[Admin Only]** Create a new product with images uploaded to Cloudflare R2.

    - `sizes` and `colors` must be JSON strings e.g. `["S", "M"]`
    - Images are uploaded to R2 and public URLs are stored in MongoDB.
    """
    # 1. Upload all images to R2
    uploaded_urls = []
    for file in image_files:
        content = await file.read()
        url = await upload_image_to_r2(content, file.filename)
        uploaded_urls.append(url)

    # 2. Parse JSON string fields
    try:
        sizes_list = json.loads(sizes)
        colors_list = json.loads(colors)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="`sizes` and `colors` must be valid JSON arrays e.g. [\"S\", \"M\"]",
        )

    # 3. Build product document
    product_doc = {
        "name": name,
        "description": description,
        "price": price,
        "category": category,
        "stock": stock,
        "sizes": sizes_list,
        "colors": colors_list,
        "images": uploaded_urls,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }

    # 4. Save to MongoDB
    result = await product_collection.insert_one(product_doc)

    return {
        "message": "Product created successfully",
        "product_id": str(result.inserted_id),
        "images": uploaded_urls,
    }


@router.get("")
async def get_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),  # Standard e-commerce grid size
):
    """
    **[Public]** Advanced product discovery with:
    - **Filtering**: `category`, `size`, `min_price`, `max_price`
    - **Search**: Case-insensitive text match on `name` and `description`
    - **Pagination**: `page` and `limit` (default: 12 per page)

    Only returns active products (`is_active: true`).
    """
    # 1. Build dynamic MongoDB filter
    query: dict = {"is_active": True}

    if category:
        query["category"] = category

    if size:
        query["sizes"] = size  # Matches if value exists in the array

    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price

    if search:
        # Case-insensitive regex search across name and description
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    # 2. Execute with pagination
    skip = (page - 1) * limit
    products = await product_collection.find(query).skip(skip).limit(limit).to_list(limit)

    return products


# ==========================================
# REVIEWS & RATINGS
# ==========================================

@router.post("/{product_id}/reviews", status_code=status.HTTP_201_CREATED)
async def submit_review(
    product_id: str,
    rating: int = Form(..., ge=1, le=5),
    comment: str = Form(..., min_length=1, max_length=1000),
    image_file: Optional[UploadFile] = File(None),
    current_user_email: str = Depends(get_current_user),
):
    """
    **[Authenticated]** Submit a review for a purchased and delivered product.
    - Validates that the customer bought the item and received it before allowing a review.
    - Updates the overall `average_rating` and `review_count` for the product.
    """
    try:
        p_id = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID format")

    # 1. Check if the product exists
    product = await product_collection.find_one({"_id": p_id, "is_active": True})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # 2. Check if the user has a "delivered" order containing this product
    order = await order_collection.find_one({
        "user_email": current_user_email,
        "status": "delivered",
        "items.product_id": product_id
    })

    if not order:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review products that you have successfully purchased and received."
        )

    # 3. Handle optional image upload
    image_url = None
    if image_file:
        content = await image_file.read()
        image_url = await upload_image_to_r2(content, image_file.filename)

    # 4. Save the review
    review_doc = {
        "product_id": product_id,
        "user_email": current_user_email,
        "rating": rating,
        "comment": comment,
        "image_url": image_url,
        "created_at": datetime.utcnow()
    }
    await review_collection.insert_one(review_doc)

    # 5. Update the product's average rating dynamically
    old_count = product.get("review_count", 0)
    old_average = product.get("average_rating", 0.0)

    new_count = old_count + 1
    new_average = ((old_average * old_count) + rating) / new_count

    await product_collection.update_one(
        {"_id": p_id},
        {"$set": {"review_count": new_count, "average_rating": round(new_average, 1)}}
    )

    return {"message": "Review submitted successfully!"}


@router.get("/{product_id}/reviews")
async def get_product_reviews(product_id: str, skip: int = 0, limit: int = 20):
    """
    **[Public]** View all reviews for a specific product.
    Sorted chronologically from newest to oldest.
    """
    reviews = await review_collection.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return reviews
