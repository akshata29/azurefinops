"""Application configuration via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    use_mock: bool = True
    data_backend: str = "adx"  # "adx" | "storage"

    azure_client_id: str = ""
    azure_client_secret: str = ""

    adx_cluster_uri: str = ""
    adx_database: str = "Hub"

    cors_origins: str = "http://localhost:5174,http://localhost:4173,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
