from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str

    # JWT Security
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # Cloudflare R2 Storage
    cf_r2_access_key_id: str
    cf_r2_secret_access_key: str
    cf_r2_endpoint_url: str
    cf_r2_public_url: str
    cf_r2_bucket_name: str

    # Resend API
    resend_api_key: str

    # Redis Cache Engine
    redis_url: str = "redis://default:shailoom2026@38.242.210.28:6380"

    # App
    app_name: str = "Shailoom E-commerce API"
    debug: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


# Global settings singleton
settings = Settings()
