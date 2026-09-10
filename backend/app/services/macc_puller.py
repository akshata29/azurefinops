"""MACC puller — reads commitment balances and drawdown events via REST.

This is the piece the FinOps toolkit does NOT provide. It calls the Azure
Billing/Consumption REST APIs with a per-affiliate token from the central
multi-tenant app, and returns normalized rows to persist into the central
store (ADX `MaccBalance` / `FactMaccEvent`).

Endpoints:
  lots   GET .../billingAccounts/{ba}/providers/Microsoft.Consumption/lots
         ?api-version=2021-05-01&$filter=source eq 'ConsumptionCommitment'
  events GET .../billingAccounts/{ba}/providers/Microsoft.Consumption/events
         ?api-version=2021-05-01&startDate=&endDate=&$filter=lotSource eq 'ConsumptionCommitment'
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_ARM = "https://management.azure.com"
_API_VERSION = "2021-05-01"
_SCOPE = "https://management.azure.com/.default"


class MaccPuller:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _token(self, tenant_id: str) -> str:
        """Acquire a token for a specific affiliate tenant (multi-tenant app)."""
        from azure.identity import ClientSecretCredential  # lazy import

        cred = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=self.settings.azure_client_id,
            client_secret=self.settings.azure_client_secret,
        )
        return cred.get_token(_SCOPE).token

    def fetch_lots(self, tenant_id: str, billing_account: str) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self._token(tenant_id)}"}
        url = f"{_ARM}/providers/Microsoft.Billing/billingAccounts/{billing_account}/providers/Microsoft.Consumption/lots"
        params = {"api-version": _API_VERSION, "$filter": "source eq 'ConsumptionCommitment'"}
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json().get("value", [])

    def fetch_events(
        self, tenant_id: str, billing_account: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self._token(tenant_id)}"}
        url = f"{_ARM}/providers/Microsoft.Billing/billingAccounts/{billing_account}/providers/Microsoft.Consumption/events"
        params = {
            "api-version": _API_VERSION,
            "startDate": start_date,
            "endDate": end_date,
            "$filter": "lotSource eq 'ConsumptionCommitment'",
        }
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json().get("value", [])

    @staticmethod
    def normalize_lot(affiliate_id: str, lot: dict[str, Any]) -> dict[str, Any]:
        p = lot.get("properties", {})
        return {
            "affiliate_id": affiliate_id,
            "commitment_amount": (p.get("originalAmount") or {}).get("value"),
            "remaining_balance": (p.get("closedBalance") or {}).get("value"),
            "currency": (p.get("originalAmount") or {}).get("currency"),
            "start_date": p.get("startDate"),
            "end_date": p.get("expirationDate"),
            "status": p.get("status"),
            "source": p.get("source"),
        }
