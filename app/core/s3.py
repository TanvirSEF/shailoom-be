import io
import uuid

from aiobotocore.session import get_session
from fastapi import HTTPException, status
from PIL import Image

from app.core.config import settings

# 5MB Limit
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


async def upload_image_to_r2(
    file_content: bytes,
    file_name: str,
) -> str:
    """
    Validate, Compress, and Upload an image to Cloudflare R2.

    - Validates file size is <= 5MB.
    - Automagically converts any image (JPEG/PNG/HEIC/etc) to WebP format.
    - Uses 90% quality optimization to ensure top-tier visual fidelity while vastly reducing file size.
    - Uses aiobotocore for async non-blocking uploads.
    """
    
    # 1. Size Validation (5MB Limit)
    if len(file_content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image -> {file_name} exceeds the maximum allowed size of 5MB."
        )

    # 2. Open Image and Convert to WebP format
    try:
        # Load image into Pillow
        image = Image.open(io.BytesIO(file_content))
        
        # Strip alpha channel / transparency if converting from PNG to ensure compatibility
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Create an in-memory byte buffer
        img_byte_arr = io.BytesIO()
        
        # Compress and save to buffer
        image.save(img_byte_arr, format="WEBP", quality=90, optimize=True)
        
        # Get the optimized byte content
        optimized_content = img_byte_arr.getvalue()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format or corrupted file: {file_name}"
        )

    # 3. Generate a WebP unique key
    unique_key = f"products/{uuid.uuid4()}.webp"

    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=settings.cf_r2_endpoint_url,
        aws_access_key_id=settings.cf_r2_access_key_id,
        aws_secret_access_key=settings.cf_r2_secret_access_key,
        region_name="auto",  # R2 uses 'auto' as region
    ) as client:
        await client.put_object(
            Bucket=settings.cf_r2_bucket_name,
            Key=unique_key,
            Body=optimized_content,
            ContentType="image/webp",
        )

    return f"{settings.cf_r2_public_url}/{unique_key}"
