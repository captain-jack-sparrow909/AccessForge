import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AccessForge API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./accessforge.db"
    redis_url: str = "redis://localhost:6379/0"
    auto_create_db: bool = True
    cors_origins: str = "http://localhost:3000"
    backend_token_issuer: str = "accessforge-web"
    backend_token_audience: str = "accessforge-api"
    backend_token_public_keys_json: str = "{}"
    allowed_web_origins: str = "http://localhost:3000"
    model_credential_encryption_key: str | None = Field(default=None, repr=False)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def public_key_map(self) -> dict[str, str]:
        try:
            value = json.loads(self.backend_token_public_keys_json)
        except json.JSONDecodeError as exc:
            raise ValueError("BACKEND_TOKEN_PUBLIC_KEYS_JSON must be valid JSON") from exc
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            raise ValueError("BACKEND_TOKEN_PUBLIC_KEYS_JSON must map key IDs to PEM strings")
        return value

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
