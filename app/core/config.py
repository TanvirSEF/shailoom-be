from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str

    # JWT Security
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # App
    app_name: str = "Shailoom E-commerce API"
    debug: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


# Global settings singleton
settings = Settings()
