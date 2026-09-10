"""Microsoft Graph client — real license (subscribedSkus) inventory.

License seats live in Entra ID / Microsoft 365, not in Azure Cost Management, so
we read them from Microsoft Graph ``/subscribedSkus`` per affiliate tenant. Graph
returns assigned vs. consumed seats but **no price**, so unit costs come from a
configurable price map (list-price estimates) — see :mod:`license_prices`.

Auth reuses the shared :class:`_TokenProvider` with the Graph scope. The app
registration / signed-in identity needs Graph **Organization.Read.All** (or
**Directory.Read.All**) in each affiliate tenant.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.license_prices import license_price, sku_display_name

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class GraphClient:
    """Reads license inventory from Microsoft Graph."""

    def __init__(self, token_provider: Any, cache: Any) -> None:
        self._tokens = token_provider
        self._cache = cache
        self._client = httpx.Client(timeout=60)

    def subscribed_skus(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Normalised license SKUs for a tenant: product, sku, assigned, consumed, unit_cost."""
        cache_key = f"skus:{(tenant_id or 'default').lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        rows: list[dict[str, Any]] = []
        try:
            token = self._tokens.token(tenant_id, scope=_GRAPH_SCOPE)
            url = f"{_GRAPH}/subscribedSkus"
            while url:
                resp = self._client.get(url, headers={"Authorization": f"Bearer {token}"})
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("value", []):
                    part = item.get("skuPartNumber") or item.get("skuId") or "UNKNOWN"
                    prepaid = item.get("prepaidUnits") or {}
                    assigned = int(prepaid.get("enabled") or 0)
                    consumed = int(item.get("consumedUnits") or 0)
                    if assigned == 0 and consumed == 0:
                        continue
                    rows.append(
                        {
                            "product": sku_display_name(part),
                            "sku": part,
                            "assigned": assigned,
                            "consumed": consumed,
                            "unit_cost": license_price(part),
                        }
                    )
                url = data.get("@odata.nextLink") or ""
        except Exception as exc:  # pragma: no cover - permission/consent
            logger.info("subscribedSkus for tenant %s unavailable: %s", tenant_id or "default", exc)
        rows.sort(key=lambda r: r["assigned"], reverse=True)
        self._cache.set(cache_key, rows)
        return rows
