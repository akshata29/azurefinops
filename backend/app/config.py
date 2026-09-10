"""Application configuration via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    use_mock: bool = True
    data_backend: str = "azure"  # "azure" | "adx" | "storage"

    # Multi-tenant app (client-credentials) — optional. When blank, live mode
    # falls back to DefaultAzureCredential (az login / managed identity / env).
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Subscriptions to treat as affiliates. Blank = discover every subscription
    # the signed-in identity can read via ARM.
    azure_subscription_ids: str = ""

    # Path to an affiliate registry JSON (maps affiliates -> tenants/subscriptions).
    # Blank = auto-detect ./affiliates.json, else fall back to subscription discovery.
    affiliate_registry: str = ""

    # Optional JSON overriding license list prices by skuPartNumber (negotiated pricing).
    license_price_map: str = ""

    # GitHub Copilot (external seats). Token needs manage_billing:copilot / read:org.
    github_token: str = ""
    github_orgs: str = ""  # comma-separated org logins; or set per-affiliate in the registry
    github_copilot_seat_cost: float = 39.0  # USD/seat/month (Enterprise; Business ~19)
    m365_copilot_seat_cost: float = 30.0  # USD/seat/month

    @property
    def github_org_list(self) -> list[str]:
        return [o.strip() for o in self.github_orgs.split(",") if o.strip()]

    # How far back to pull historical cost data (months). Cost Management retains
    # ~13 months for most offers; the client stops early when data runs out.
    history_months: int = 13

    # In-memory cache TTL (seconds) for expensive Cost Management queries.
    cache_ttl_seconds: int = 3600

    # Directory for the permanent monthly cost-history store (closed months are
    # immutable, so they are fetched once and kept forever — only the open month
    # is refreshed). Blank = <backend>/data/cost_history.
    cost_history_dir: str = ""

    # Days after month-rollover during which the just-closed prior month is still
    # treated as "open" (re-fetched) because late usage can still settle into it.
    # Outside this window only the current month is refreshed (~1 QPU/query).
    cost_settle_days: int = 5

    # Minimum spacing (seconds) between Cost Management API calls. A global pacer
    # spaces every request this far apart so concurrent dashboard/polling
    # requests can't burst past the API's per-subscription rate limit (HTTP 429).
    cost_min_request_interval: float = 0.7

    adx_cluster_uri: str = ""
    adx_database: str = "Hub"

    cors_origins: str = "http://localhost:5174,http://localhost:4173,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def subscription_id_list(self) -> list[str]:
        return [s.strip() for s in self.azure_subscription_ids.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
