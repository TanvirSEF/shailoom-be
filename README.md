# Shailoom E-commerce Backend API

A production-ready FastAPI backend for the Shailoom clothing brand, powered by MongoDB Atlas and Cloudflare R2.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | MongoDB Atlas (Motor async driver) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Storage | Cloudflare R2 (aiobotocore) |
| Config | pydantic-settings |

## Project Structure

```
shailoom-be/
├── app/
│   ├── core/
│   │   ├── config.py      # All settings from .env
│   │   ├── database.py    # MongoDB client & collections
│   │   ├── security.py    # JWT utils & auth dependencies
│   │   └── s3.py          # Cloudflare R2 upload utility
│   ├── models/
│   │   ├── product.py
│   │   ├── user.py
│   │   └── order.py
│   ├── routers/
│   │   ├── auth.py        # /auth/signup, /auth/login
│   │   ├── products.py    # /products
│   │   ├── orders.py      # /orders
│   │   └── admin.py       # /admin/*
│   └── main.py            # App factory
├── main.py                # Entrypoint
├── .env                   # (not committed)
└── requirements.txt
```

## Getting Started

### 1. Create & activate virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the project root:
```env
MONGODB_URL=mongodb+srv://...
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

CF_R2_ACCESS_KEY_ID=your_r2_key
CF_R2_SECRET_ACCESS_KEY=your_r2_secret
CF_R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
CF_R2_PUBLIC_URL=https://pub-xxxx.r2.dev
CF_R2_BUCKET_NAME=shailoom-media
```

### 4. Run the development server
```bash
uvicorn main:app --reload
```

Visit **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

## API Overview

### Authentication
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/signup` | Public | Register new user, returns JWT |
| `POST` | `/auth/login` | Public | Login, returns JWT |

### Products
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/products` | Admin | Create product + upload images to R2 |
| `GET` | `/products` | Public | List products (filter, search, paginate) |

**Query params for `GET /products`:** `category`, `size`, `min_price`, `max_price`, `search`, `page`, `limit`

### Orders
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/orders` | User | Place order (atomic stock decrement) |
| `GET` | `/orders/track/{id}` | Public | Track order by tracking ID |

### Admin
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/admin/orders` | Admin | View all orders |
| `PATCH` | `/admin/orders/{id}` | Admin | Update order/payment status |

### Health
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Public | Health check |

## Recommended MongoDB Indexes

Run in Atlas UI or Compass under the `products` collection:

```json
// Fast category + price filtering
{ "category": 1, "price": 1 }

// Text search on name and description
{ "name": "text", "description": "text" }
```
