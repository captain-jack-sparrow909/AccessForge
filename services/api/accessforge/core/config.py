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
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket_private: str = "accessforge-private"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = Field(default="minioadmin", repr=False)
    asset_presign_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    asset_max_bytes: int = Field(default=100_000_000, ge=1_000, le=1_000_000_000)
    asset_retention_days: int = Field(default=30, ge=1, le=3650)
    default_model_provider: str = "none"
    deepseek_api_key: str | None = Field(default=None, repr=False)
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_fast_model: str = "deepseek-v4-flash"
    deepseek_reasoning_model: str = "deepseek-v4-pro"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_api_base: str = "https://api.openai.com/v1"
    openai_fast_model: str | None = None
    openai_reasoning_model: str | None = None
    anthropic_api_key: str | None = Field(default=None, repr=False)
    anthropic_fast_model: str | None = None
    anthropic_reasoning_model: str | None = None
    google_api_key: str | None = Field(default=None, repr=False)
    google_fast_model: str | None = None
    google_reasoning_model: str | None = None
    custom_model_endpoint_allowlist: str = ""
    allow_unsafe_custom_model_endpoints: bool = False
    model_provider_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)

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

    @property
    def custom_model_endpoint_allowlist_values(self) -> set[str]:
        return {
            hostname.strip().lower()
            for hostname in self.custom_model_endpoint_allowlist.split(",")
            if hostname.strip()
        }

    def managed_provider_key(self, provider_type: str) -> str | None:
        return {
            "deepseek": self.deepseek_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_api_key,
        }.get(provider_type)


@lru_cache
def get_settings() -> Settings:
    return Settings()
