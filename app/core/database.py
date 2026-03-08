import certifi
import motor.motor_asyncio

from app.core.config import settings

# Create the async MongoDB client using the URL from settings
client = motor.motor_asyncio.AsyncIOMotorClient(
    settings.mongodb_url,
    tlsCAFile=certifi.where()
)

# Select the database
database = client.shailoom

# --- Collections ---
product_collection = database.get_collection("products")
user_collection = database.get_collection("users")
order_collection = database.get_collection("orders")
