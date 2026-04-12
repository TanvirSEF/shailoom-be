import certifi
import motor.motor_asyncio
from app.core.config import settings

# MongoDB Setup
MONGODB_URL = settings.mongodb_url
client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGODB_URL,
    tls=True,
    tlsCAFile=certifi.where() 
)
db = client.get_database("shailoom_db")

# MongoDB Collections
user_collection = db.get_collection("users")
product_collection = db.get_collection("products")
order_collection = db.get_collection("orders")
review_collection = db.get_collection("reviews")
coupon_collection = db.get_collection("coupons")
audit_collection = db.get_collection("audit_logs")
