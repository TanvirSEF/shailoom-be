import certifi
import motor.motor_asyncio
import redis.asyncio as redis
from app.core.config import settings

# MongoDB Setup
MONGODB_URL = settings.mongodb_url
client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGODB_URL,
    tls=True,
    tlsCAFile="/etc/ssl/certs/ca-certificates.crt"  # Trust system root certificates
)
db = client.get_database("shailoom_db")

# MongoDB Collections
user_collection = db.get_collection("users")
product_collection = db.get_collection("products")
order_collection = db.get_collection("orders")
review_collection = db.get_collection("reviews")
coupon_collection = db.get_collection("coupons")
audit_collection = db.get_collection("audit_logs")

# Redis Cache Client Setup
redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
