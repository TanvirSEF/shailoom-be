"""
MongoDB Schema Validation & Index Management for Shailoom.

This module defines:
  - JSON Schema validators for each collection (enforced at DB level)
  - Index definitions for query performance
  - Lifecycle management (create/verify on startup)

Schema validation prevents corrupt/invalid data from being inserted
even if someone accesses MongoDB directly (bypassing the API).
"""


# ============================================================
# JSON Schema Validators (MongoDB $jsonSchema)
# ============================================================

USERS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["email", "username", "role"],
        "properties": {
            "email": {
                "bsonType": "string",
                "description": "User email (unique identifier for auth)",
            },
            "username": {"bsonType": "string"},
            "phone_number": {"bsonType": "string"},
            "address": {"bsonType": "string"},
            "role": {
                "bsonType": "string",
                "enum": ["customer", "admin"],
                "description": "Must be 'customer' or 'admin'",
            },
            "password_hash": {"bsonType": "string"},
            "wishlist": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
            },
            "reset_token": {"bsonType": "string"},
            "reset_token_expiry": {"bsonType": "date"},
            "created_at": {"bsonType": "date"},
        },
    }
}

PRODUCTS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "description", "price", "category"],
        "properties": {
            "name": {"bsonType": "string"},
            "description": {"bsonType": "string"},
            "price": {"bsonType": "double", "minimum": 0},
            "original_price": {"bsonType": "double"},
            "category": {"bsonType": "string"},
            "fabric": {"bsonType": "string"},
            "shipping_fee_inside_dhaka": {"bsonType": "double", "minimum": 0},
            "shipping_fee_outside_dhaka": {"bsonType": "double", "minimum": 0},
            "sizes": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
            },
            "colors": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
            },
            "stock": {"bsonType": "int", "minimum": 0},
            "images": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
            },
            "average_rating": {"bsonType": "double", "minimum": 0, "maximum": 5},
            "review_count": {"bsonType": "int", "minimum": 0},
            "is_active": {"bsonType": "bool"},
            "is_new_arrival": {"bsonType": "bool"},
            "is_on_sale": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"},
        },
    }
}

ORDERS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_email", "items", "total_amount", "tracking_id", "shipping_address", "shipping_zone", "phone_number"],
        "properties": {
            "user_email": {"bsonType": "string"},
            "items": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["product_id", "name", "quantity", "price", "size", "color"],
                    "properties": {
                        "product_id": {"bsonType": "string"},
                        "name": {"bsonType": "string"},
                        "quantity": {"bsonType": "int", "minimum": 1},
                        "price": {"bsonType": "double", "minimum": 0},
                        "size": {"bsonType": "string"},
                        "color": {"bsonType": "string"},
                    },
                },
            },
            "total_amount": {"bsonType": "double", "minimum": 0},
            "shipping_address": {"bsonType": "string"},
            "shipping_zone": {"bsonType": "string"},
            "phone_number": {"bsonType": "string"},
            "payment_method": {"bsonType": "string"},
            "shipping_fee": {"bsonType": "double", "minimum": 0},
            "tax_amount": {"bsonType": "double", "minimum": 0},
            "discount_amount": {"bsonType": "double", "minimum": 0},
            "coupon_code": {"bsonType": "string"},
            "status": {
                "bsonType": "string",
                "enum": ["pending", "confirmed", "shipped", "delivered", "cancelled"],
            },
            "payment_status": {
                "bsonType": "string",
                "enum": ["unpaid", "paid"],
            },
            "tracking_id": {"bsonType": "string"},
            "steadfast_consignment_id": {"bsonType": "string"},
            "steadfast_status": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

REVIEWS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["product_id", "user_email", "rating", "comment"],
        "properties": {
            "product_id": {"bsonType": "string"},
            "user_email": {"bsonType": "string"},
            "rating": {"bsonType": "int", "minimum": 1, "maximum": 5},
            "comment": {"bsonType": "string"},
            "image_url": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

COUPONS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["code", "discount_type", "discount_value", "end_date"],
        "properties": {
            "code": {"bsonType": "string"},
            "discount_type": {
                "bsonType": "string",
                "enum": ["percentage", "fixed"],
            },
            "discount_value": {"bsonType": "double", "minimum": 0},
            "min_order_value": {"bsonType": "double", "minimum": 0},
            "start_date": {"bsonType": "date"},
            "end_date": {"bsonType": "date"},
            "usage_limit": {"bsonType": "int", "minimum": 0},
            "used_count": {"bsonType": "int", "minimum": 0},
            "is_active": {"bsonType": "bool"},
        },
    }
}

AUDIT_LOGS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["admin_email", "action"],
        "properties": {
            "admin_email": {"bsonType": "string"},
            "action": {"bsonType": "string"},
            "details": {"bsonType": "string"},
            "timestamp": {"bsonType": "date"},
        },
    }
}


# ============================================================
# Index Definitions
# ============================================================

import pymongo

# Each entry: (collection_name, index_spec, unique, name)
INDEX_DEFINITIONS = [
    # --- Products ---
    ("products", [("category", pymongo.ASCENDING), ("price", pymongo.ASCENDING)], False, "category_price_idx"),
    ("products", [("name", pymongo.TEXT), ("description", pymongo.TEXT)], False, "name_description_text_idx"),
    ("products", [("is_active", pymongo.ASCENDING)], False, "products_active_idx"),
    ("products", [("is_new_arrival", pymongo.ASCENDING)], False, "products_new_arrival_idx"),
    ("products", [("is_on_sale", pymongo.ASCENDING)], False, "products_on_sale_idx"),
    ("products", [("created_at", pymongo.DESCENDING)], False, "products_created_at_idx"),
    ("products", [("fabric", pymongo.ASCENDING)], False, "products_fabric_idx"),

    # --- Users ---
    ("users", [("email", pymongo.ASCENDING)], True, "users_email_unique"),
    ("users", [("role", pymongo.ASCENDING)], False, "users_role_idx"),
    ("users", [("created_at", pymongo.DESCENDING)], False, "users_created_at_idx"),

    # --- Orders ---
    ("orders", [("tracking_id", pymongo.ASCENDING)], True, "orders_tracking_id_unique"),
    ("orders", [("user_email", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)], False, "orders_user_date_idx"),
    ("orders", [("status", pymongo.ASCENDING)], False, "orders_status_idx"),
    ("orders", [("created_at", pymongo.DESCENDING)], False, "orders_created_at_idx"),
    ("orders", [("payment_status", pymongo.ASCENDING)], False, "orders_payment_status_idx"),

    # --- Reviews ---
    ("reviews", [("product_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)], False, "reviews_product_date_idx"),
    ("reviews", [("user_email", pymongo.ASCENDING)], False, "reviews_user_idx"),

    # --- Coupons ---
    ("coupons", [("code", pymongo.ASCENDING)], True, "coupons_code_unique"),
    ("coupons", [("is_active", pymongo.ASCENDING)], False, "coupons_active_idx"),
    ("coupons", [("end_date", pymongo.ASCENDING)], False, "coupons_end_date_idx"),

    # --- Audit Logs ---
    ("audit_logs", [("timestamp", pymongo.DESCENDING)], False, "audit_timestamp_idx"),
    ("audit_logs", [("admin_email", pymongo.ASCENDING)], False, "audit_admin_idx"),
]


# ============================================================
# Schema-to-Collection mapping
# ============================================================

COLLECTION_VALIDATORS = {
    "users": USERS_VALIDATOR,
    "products": PRODUCTS_VALIDATOR,
    "orders": ORDERS_VALIDATOR,
    "reviews": REVIEWS_VALIDATOR,
    "coupons": COUPONS_VALIDATOR,
    "audit_logs": AUDIT_LOGS_VALIDATOR,
}
