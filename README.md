# Shailoom E-commerce Backend API

A production-ready FastAPI backend for the Shailoom clothing brand, powered by MongoDB Atlas.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | MongoDB Atlas (via Motor async driver) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Config | pydantic-settings |

## Project Structure

```
shailoom-be/
├── app/
│   ├── core/
│   │   ├── config.py      # App settings from .env
│   │   ├── database.py    # MongoDB client & collections
│   │   └── security.py    # JWT utils & auth dependencies
│   ├── models/
│   │   ├── product.py
│   │   ├── user.py
│   │   └── order.py
│   ├── routers/
│   │   ├── products.py    # /products
│   │   ├── orders.py      # /orders
│   │   └── admin.py       # /admin/*
│   └── main.py            # App factory
├── main.py                # Entrypoint
├── .env                   # (not committed)
└── requirements.txt
```

## Getting Started

### 1. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the project root:
```
MONGODB_URL=mongodb+srv://...
SECRET_KEY=your-super-secret-key
```

### 4. Run the development server
```bash
uvicorn main:app --reload
```

Visit **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

## API Overview

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Public | Health check |
| `POST` | `/products` | Admin | Add a product |
| `GET` | `/products` | Public | List all products |
| `POST` | `/orders` | User | Place an order |
| `GET` | `/orders/track/{id}` | Public | Track an order |
| `GET` | `/admin/orders` | Admin | View all orders |
| `PATCH` | `/admin/orders/{id}` | Admin | Update order status |
