import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.database import product_collection
from app.core.s3 import upload_image_to_r2
from app.core.security import get_current_admin
from app.models.product import ProductModel

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    stock: int = Form(...),
    sizes: str = Form(..., example='["S", "M", "L", "XL"]'),
    colors: str = Form(..., example='["Red", "Blue"]'),
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
        url = await upload_image_to_r2(content, file.filename, file.content_type)
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


@router.get("", response_model=List[ProductModel])
async def get_all_products():
    """
    **[Public]** Retrieve all active products from the store.
    """
    products = await product_collection.find().to_list(100)
    return products
