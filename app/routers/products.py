from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import product_collection
from app.core.security import get_current_admin
from app.models.product import ProductModel

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductModel,
    admin_user: str = Depends(get_current_admin),
):
    """
    **[Admin Only]** Add a new product to the store.
    Requires a valid JWT token with role `admin`.
    """
    product_data = product.dict()
    result = await product_collection.insert_one(product_data)

    if result.inserted_id:
        return {
            "message": "Product added successfully",
            "id": str(result.inserted_id),
        }
    raise HTTPException(status_code=500, detail="Failed to create product")


@router.get("", response_model=List[ProductModel])
async def get_all_products():
    """
    **[Public]** Retrieve all active products from the store.
    """
    products = await product_collection.find().to_list(100)
    return products
