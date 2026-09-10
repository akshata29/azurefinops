"""License display names + list-price estimates by Entra ``skuPartNumber``.

Microsoft Graph exposes seat counts but not price. These are public list-price
estimates (USD / seat / month) used to value license spend; override via a JSON
file pointed at by ``LICENSE_PRICE_MAP`` to reflect your negotiated pricing.
Unknown SKUs get a price of 0 (counted, not valued) rather than a fabricated one.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

# skuPartNumber -> (display name, list price USD/seat/month)
_DEFAULTS: dict[str, tuple[str, float]] = {
    "ENTERPRISEPREMIUM": ("Office 365 E5", 38.0),
    "ENTERPRISEPACK": ("Office 365 E3", 23.0),
    "SPE_E5": ("Microsoft 365 E5", 57.0),
    "SPE_E3": ("Microsoft 365 E3", 36.0),
    "SPE_F1": ("Microsoft 365 F3", 8.0),
    "SPB": ("Microsoft 365 Business Premium", 22.0),
    "O365_BUSINESS_PREMIUM": ("Microsoft 365 Business Standard", 12.5),
    "O365_BUSINESS_ESSENTIALS": ("Microsoft 365 Business Basic", 6.0),
    "POWER_BI_PRO": ("Power BI Pro", 10.0),
    "POWER_BI_PREMIUM_PER_USER": ("Power BI Premium (per user)", 20.0),
    "FLOW_FREE": ("Power Automate Free", 0.0),
    "POWERAPPS_PER_USER": ("Power Apps (per user)", 20.0),
    "EMS": ("Enterprise Mobility + Security E3", 10.6),
    "EMSPREMIUM": ("Enterprise Mobility + Security E5", 16.4),
    "AAD_PREMIUM": ("Entra ID P1", 6.0),
    "AAD_PREMIUM_P2": ("Entra ID P2", 9.0),
    "MCOEV": ("Teams Phone", 8.0),
    "MCOMEETADV": ("Teams Audio Conferencing", 4.0),
    "PROJECTPROFESSIONAL": ("Project Plan 3", 30.0),
    "PROJECTPREMIUM": ("Project Plan 5", 55.0),
    "VISIOCLIENT": ("Visio Plan 2", 15.0),
    "DYN365_ENTERPRISE_SALES": ("Dynamics 365 Sales Enterprise", 95.0),
    "Microsoft_365_Copilot": ("Microsoft 365 Copilot", 30.0),
    "MICROSOFT_365_COPILOT": ("Microsoft 365 Copilot", 30.0),
    "WIN_ENT_E3": ("Windows 10/11 Enterprise E3", 7.0),
    "DEVELOPERPACK_E5": ("Microsoft 365 E5 Developer", 0.0),
}

_overrides: dict[str, tuple[str, float]] | None = None


def _load_overrides() -> dict[str, tuple[str, float]]:
    global _overrides
    if _overrides is not None:
        return _overrides
    _overrides = {}
    path_str = get_settings().license_price_map
    if path_str:
        path = Path(path_str).expanduser()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for sku, entry in raw.items():
                    if isinstance(entry, dict):
                        _overrides[sku] = (str(entry.get("name") or sku), float(entry.get("unit_cost") or 0.0))
                    else:  # bare number = price, keep default name
                        _overrides[sku] = (sku, float(entry))
                logger.info("Loaded %d license price override(s) from %s", len(_overrides), path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                logger.error("Failed to read license price map %s: %s", path, exc)
    return _overrides


def _lookup(sku_part: str) -> tuple[str, float]:
    over = _load_overrides()
    if sku_part in over:
        name, price = over[sku_part]
        if sku_part in _DEFAULTS and name == sku_part:
            name = _DEFAULTS[sku_part][0]
        return name, price
    return _DEFAULTS.get(sku_part, (sku_part, 0.0))


def sku_display_name(sku_part: str) -> str:
    return _lookup(sku_part)[0]


def license_price(sku_part: str) -> float:
    return _lookup(sku_part)[1]
