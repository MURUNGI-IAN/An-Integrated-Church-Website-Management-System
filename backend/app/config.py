import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./church.db"
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    jwt_secret: str = ""
    data_encryption_key: str = ""
    access_token_minutes: int = 30

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_production_secrets(self) -> None:
        if self.database_url.startswith("sqlite"):
            return
        if len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters in production")
        if not self.data_encryption_key:
            raise RuntimeError("DATA_ENCRYPTION_KEY is required for production deployments")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()