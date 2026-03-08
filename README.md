# Shailoom E-commerce Backend API

A production-ready FastAPI backend for the Shailoom clothing brand. Highly optimized for performance with Caching, DDoS protection, Image Optimization, and cloud storage via Cloudflare R2.

## Tech Stack & Core Features

| Feature | Technology | Description |
|---|---|---|
| **Framework** | FastAPI | High performance async web framework |
| **Database** | MongoDB Atlas | Motor async driver with automated indexing |
| **Caching** | Redis (`redis.asyncio`) | 5-minute TTL caching for fast product discovery |
| **Security & Auth** | JWT + bcrypt | Secure password hashing, Role-based ACL |
| **Rate Limiting** | SlowAPI | Global 100 req/min limits for DDoS & Bot protection |
| **Storage & Media** | Cloudflare R2 + Pillow | 5MB upload limit, on-the-fly WebP compression |
| **Email Service** | Resend API | Secure, token-based "Forgot Password" flow |
| **Config** | Pydantic Settings | Environment variable management |
| **Logging** | Python Logging | Centralized `app.log` with auto-rotation (<5MB) |

## Project Features

- **Storefront**: Advanced product filtering, text search, pagination.
- **Cart & Orders**: Atomic stock decrement, secure checkout, order tracking.
- **Coupons**: Percentage and fixed discount promo codes.
- **User Activity**: Wishlists, product reviews, and ratings.
- **Admin Dashboard**: Sales analytics, low-stock alerts, user management, order status updates.
- **SEO**: Dynamic `sitemap.xml` generation.
- **Deployment**: Configured for PaaS like Dokploy / Heroku (`nixpacks.toml`, `Procfile`).

## Getting Started

### 1. Requirements
- Python 3.12+
- MongoDB instance (local or Atlas)
- Redis server
- Cloudflare R2 bucket
- Resend API key

### 2. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root:
```env
# Database & Cache
MONGODB_URL=mongodb+srv://...
REDIS_URL=redis://default:shailoom2026@38.242.210.28:6380

# Security (Auth & Passwords)
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Third-party Integrations
RESEND_API_KEY=your_resend_api_key

# Cloudflare R2 Storage
CF_R2_ACCESS_KEY_ID=your_r2_key
CF_R2_SECRET_ACCESS_KEY=your_r2_secret
CF_R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
CF_R2_PUBLIC_URL=https://pub-xxxx.r2.dev
CF_R2_BUCKET_NAME=shailoom-media
```

### 4. Run the Development Server
```bash
uvicorn main:app --reload
```
Visit **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

## API Overview (Key Endpoints)

- **Authentication**: `POST /auth/signup`, `POST /auth/login`, `POST /auth/forgot-password`, `POST /auth/reset-password`
- **Products**: `GET /products` (Cached), `POST /products/{id}/reviews`
- **Orders & Checkout**: `POST /orders`, `GET /orders/track/{id}`, `GET /orders/validate-coupon`
- **User**: `GET /users/me`, `GET /users/me/wishlist`, `GET /orders/my-orders`
- **Admin Analytics**: `GET /admin/analytics/sales`, `GET /admin/analytics/low-stock`
- **Admin Management**: `POST /admin/coupons`, `PATCH /admin/users/{email}/role`
- **SEO**: `GET /sitemap.xml`

## Deployment

This project includes `nixpacks.toml` and a `Procfile` for seamless deployment to platforms like **Dokploy**, **Railway**, or **Heroku**. 
Ensure all environment variables from `.env` are configured in your hosting provider's dashboard.
