import json
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
    Request, # Added Request
    BackgroundTasks
)

from bson import ObjectId
from app.core.database import order_collection, product_collection, review_collection, redis_client # Added redis_client
from app.core.s3 import upload_image_to_r2, delete_image_from_r2
from app.core.security import get_current_admin, get_current_user
from app.models.product import ProductModel
from app.models.review import ReviewModel # Kept ReviewModel

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


@router.get("/search/suggestions")
async def get_search_suggestions(q: str = Query(..., min_length=2, max_length=50)):
    """
    **[Public]** Fast autocomplete suggestions for the storefront search bar.
    Returns highly compact JSON (< 1KB) to ensure instant frontend rendering.
    """
    query = {
        "is_active": True,
        "name": {"$regex": q, "$options": "i"}
    }
    # Only fetch _id, name, price, and the VERY FIRST image in the array
    cursor = product_collection.find(query, {"name": 1, "price": 1, "images": {"$slice": 1}}).limit(5)
    suggestions = await cursor.to_list(length=5)
    
    for s in suggestions:
        s["_id"] = str(s["_id"])
        
    return suggestions


@router.get("")
async def get_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("newest", description="Valid options: newest, price_asc, price_desc, top_rated"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),  # Standard e-commerce grid size
):
    """
    **[Public]** Advanced product discovery with:
    - **Caching**: Utlilizes Redis Cache to serve instantaneous results.
    - **Filtering**: `category`, `size`, `min_price`, `max_price`
    - **Search**: Case-insensitive text match on `name` and `description`
    - **Pagination**: `page` and `limit` (default: 12 per page)

    Only returns active products (`is_active: true`).
    """
    # 0. Deterministic Cache Key Generation
    cache_key_elements = [
        f"cat:{category or ''}",
        f"min:{min_price or ''}",
        f"max:{max_price or ''}",
        f"sz:{size or ''}",
        f"q:{search or ''}",
        f"srt:{sort_by or ''}",
        f"p:{page}",
        f"l:{limit}"
    ]
    cache_key = "products:" + "_".join(cache_key_elements)

    # 1. Check Redis Cache
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis Cache Error (Reading): {e}")

    # 2. Build dynamic MongoDB filter (Cache Miss)
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

    # 3. Execute with pagination and sorting
    skip = (page - 1) * limit
    cursor = product_collection.find(query)
    
    if sort_by == "price_asc":
        cursor = cursor.sort("price", 1)
    elif sort_by == "price_desc":
        cursor = cursor.sort("price", -1)
    elif sort_by == "top_rated":
        cursor = cursor.sort("average_rating", -1)
    else:
        # Default 'newest'
        cursor = cursor.sort("created_at", -1)

    products_cursor = await cursor.skip(skip).limit(limit).to_list(limit)

    # Serialize ObjectIds for JSON/Redis compatibility
    products = []
    for p in products_cursor:
        p["_id"] = str(p["_id"])
        products.append(p)

    # 4. Save to Redis Cache (TTL = 5 mins = 300 seconds)
    try:
        await redis_client.setex(cache_key, 300, json.dumps(products, default=str))
    except Exception as e:
        print(f"Redis Cache Error (Writing): {e}")

    return products


@router.delete("/{product_id}", dependencies=[Depends(get_current_admin)])
async def delete_product(product_id: str, background_tasks: BackgroundTasks):
    """
    **[Admin Only]** Delete a product from the database AND wipe its images from Cloudflare R2 automatically to save on storage costs.
    Utilizes BackgroundTasks so the database operation returns instantly.
    """
    try:
        p_id = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")

    product = await product_collection.find_one({"_id": p_id})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # 1. Background task to delete all images from R2
    images = product.get("images", [])
    for img_url in images:
        background_tasks.add_task(delete_image_from_r2, img_url)

    # 2. Delete the product from MongoDB
    await product_collection.delete_one({"_id": p_id})

    return {"message": "Product and associated cloud media deleted successfully"}


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
