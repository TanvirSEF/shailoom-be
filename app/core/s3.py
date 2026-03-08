import uuid

from aiobotocore.session import get_session

from app.core.config import settings


async def upload_image_to_r2(
    file_content: bytes,
    file_name: str,
    content_type: str,
) -> str:
    """
    Upload a file to Cloudflare R2 and return its public URL.

    - Generates a unique key: `products/<uuid>.<ext>`
    - Uses aiobotocore (async boto3-compatible) for non-blocking uploads.
    """
    file_ext = file_name.rsplit(".", 1)[-1].lower()
    unique_key = f"products/{uuid.uuid4()}.{file_ext}"

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
            Body=file_content,
            ContentType=content_type,
        )

    return f"{settings.cf_r2_public_url}/{unique_key}"
