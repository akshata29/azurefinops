"""Affiliate registry — the scale primitive for onboarding tenants/subscriptions.

An *affiliate* maps a business unit / customer to one or more Azure
subscriptions (optionally in its own tenant). The registry is a plain JSON file
so onboarding a new affiliate is a config change, not a code change:

    {
      "affiliates": [
        {
          "affiliate_id": "aff-001",
          "name": "Contoso Retail",
          "tenant_id": "1111....",           // omit to use the signed-in tenant
          "agreement_type": "EA",             // EA | MCA
          "billing_account": "7654321",
          "billing_profile": null,
          "subscription_ids": ["aaaa...."]
        }
      ]
    }

Resolution order:
  1. ``AFFILIATE_REGISTRY`` env / ``affiliate_registry`` setting (explicit path).
  2. ``backend/affiliates.json`` if present.
  3. Otherwise no registry — the provider falls back to auto-discovering every
     subscription the signed-in identity can read (each subscription = one
     affiliate), which is the zero-config single-tenant path.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)

_DEFAULT_FILENAMES = ("affiliates.json",)


@dataclass
class AffiliateDef:
    affiliate_id: str
    name: str
    subscription_ids: list[str]
    tenant_id: str = ""
    agreement_type: str = "MCA"
    billing_account: str = ""
    billing_profile: str | None = None
    github_orgs: list[str] = field(default_factory=list)


@dataclass
class AffiliateRegistry:
    affiliates: list[AffiliateDef] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.affiliates


def _coerce(entry: dict) -> AffiliateDef | None:
    affiliate_id = str(entry.get("affiliate_id") or entry.get("id") or "").strip()
    subs = entry.get("subscription_ids") or entry.get("subscriptions") or []
    if isinstance(subs, str):
        subs = [s.strip() for s in subs.split(",") if s.strip()]
    subs = [str(s).strip() for s in subs if str(s).strip()]
    if not affiliate_id or not subs:
        logger.warning("Skipping affiliate registry entry (needs affiliate_id + subscription_ids): %s", entry)
        return None
    orgs = entry.get("github_orgs") or entry.get("github_org") or []
    if isinstance(orgs, str):
        orgs = [o.strip() for o in orgs.split(",") if o.strip()]
    orgs = [str(o).strip() for o in orgs if str(o).strip()]
    return AffiliateDef(
        affiliate_id=affiliate_id,
        name=str(entry.get("name") or affiliate_id),
        subscription_ids=subs,
        tenant_id=str(entry.get("tenant_id") or ""),
        agreement_type=str(entry.get("agreement_type") or "MCA").upper(),
        billing_account=str(entry.get("billing_account") or ""),
        billing_profile=entry.get("billing_profile"),
        github_orgs=orgs,
    )


def _registry_path(settings: Settings) -> Path | None:
    if settings.affiliate_registry:
        p = Path(settings.affiliate_registry).expanduser()
        return p if p.exists() else None
    for name in _DEFAULT_FILENAMES:
        p = Path(name)
        if p.exists():
            return p
    return None


def load_registry(settings: Settings) -> AffiliateRegistry:
    path = _registry_path(settings)
    if path is None:
        return AffiliateRegistry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read affiliate registry %s: %s", path, exc)
        return AffiliateRegistry()
    entries = raw.get("affiliates") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        logger.error("Affiliate registry %s must contain an 'affiliates' list", path)
        return AffiliateRegistry()
    affiliates = [a for a in (_coerce(e) for e in entries if isinstance(e, dict)) if a]
    logger.info("Loaded %d affiliate(s) from registry %s", len(affiliates), path)
    return AffiliateRegistry(affiliates=affiliates)
