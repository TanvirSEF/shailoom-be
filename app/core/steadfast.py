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


def _normalize_phone(phone: str) -> str:
    """Normalize a BD phone number to exactly 11 digits (e.g. '01712345678')."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("880"):
        digits = "0" + digits[3:]
    elif digits.startswith("88"):
        digits = "0" + digits[2:]
    if not digits.startswith("0"):
        digits = "0" + digits
    return digits[:11]


def _build_item_description(order: dict) -> str:
    """Build a short item summary for Steadfast, e.g. '3x Cotton Saree, 1x Scarf'."""
    items = order.get("items") or []
    parts = []
    for item in items[:5]:
        qty = item.get("quantity", 1)
        name = item.get("name", "Item")
        if len(name) > 30:
            name = name[:28] + ".."
        parts.append(f"{qty}x {name}")
    desc = ", ".join(parts)
    if len(items) > 5:
        desc += f" +{len(items) - 5} more"
    return desc[:250]


async def create_consignment(order: dict, recipient_name: str) -> dict:
    client = await _get_client()

    phone = _normalize_phone(order.get("phone_number", ""))

    payload = {
        "invoice": order["tracking_id"],
        "recipient_name": recipient_name[:100],
        "recipient_phone": phone,
        "recipient_address": order["shipping_address"][:250],
        "cod_amount": order["total_amount"],
        "recipient_email": order.get("user_email", ""),
        "item_description": _build_item_description(order),
        "note": f"Shipping zone: {order.get('shipping_zone', 'N/A')}",
        "total_lot": sum(item.get("quantity", 1) for item in order.get("items", [])),
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


async def create_return_request(consignment_id: int | str, reason: str = "") -> dict:
    """Create a return request on Steadfast for a consignment."""
    client = await _get_client()
    payload: dict = {"consignment_id": int(consignment_id)}
    if reason:
        payload["reason"] = reason
    response = await client.post("/create_return_request", json=payload)
    response.raise_for_status()
    return response.json()
