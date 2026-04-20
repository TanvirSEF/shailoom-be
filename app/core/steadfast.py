import httpx

from app.core.config import settings
from app.core.logger import app_logger

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.steadfast_base_url,
            headers={
                "Api-Key": settings.steadfast_api_key,
                "Secret-Key": settings.steadfast_secret_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def create_consignment(order: dict, recipient_name: str) -> dict:
    client = await _get_client()
    payload = {
        "invoice": order["tracking_id"],
        "recipient_name": recipient_name,
        "recipient_phone": order["phone_number"],
        "recipient_address": order["shipping_address"],
        "cod_amount": order["total_amount"],
    }
    try:
        response = await client.post("/create_order", json=payload)
        response.raise_for_status()
        data = response.json()
        app_logger.info(f"Steadfast consignment created for order {order['tracking_id']}: {data}")
        return data
    except httpx.HTTPStatusError as e:
        app_logger.error(f"Steadfast API error for order {order['tracking_id']}: {e.response.text}")
        raise
    except httpx.RequestError as e:
        app_logger.error(f"Steadfast connection error: {e}")
        raise


async def get_status_by_consignment_id(consignment_id: int | str) -> dict:
    client = await _get_client()
    response = await client.get(f"/status_by_cid/{consignment_id}")
    response.raise_for_status()
    return response.json()


async def get_status_by_invoice(invoice: str) -> dict:
    client = await _get_client()
    response = await client.get(f"/status_by_invoice/{invoice}")
    response.raise_for_status()
    return response.json()


async def get_status_by_tracking_code(tracking_code: str) -> dict:
    client = await _get_client()
    response = await client.get(f"/status_by_trackingcode/{tracking_code}")
    response.raise_for_status()
    return response.json()


async def get_balance() -> dict:
    client = await _get_client()
    response = await client.get("/get_balance")
    response.raise_for_status()
    return response.json()
