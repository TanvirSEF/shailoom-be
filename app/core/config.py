from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str

    # JWT Security
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int = 7

    # Cloudflare R2 Storage
    cf_r2_access_key_id: str
    cf_r2_secret_access_key: str
    cf_r2_endpoint_url: str
    cf_r2_public_url: str
    cf_r2_bucket_name: str

    # Resend API
    resend_api_key: str
    sender_email: str = "Shailoom <onboarding@resend.dev>"
    admin_email: str = "shailoombangladesh@gmail.com"

    # App
    app_name: str = "Shailoom E-commerce API"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings singleton
settings = Settings()
