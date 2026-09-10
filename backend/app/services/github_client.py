"""GitHub Copilot client — real seat counts + acceptance for the AI slice.

GitHub Copilot seats and usage live in GitHub, not Azure, so we read them from the
GitHub REST API per org:

* ``GET /orgs/{org}/copilot/billing``          -> seat_breakdown (total seats)
* ``GET /orgs/{org}/copilot/metrics``          -> daily code-completion acceptance

Auth uses a token (``GITHUB_TOKEN``) with ``manage_billing:copilot`` (or
``read:org`` + Copilot). Cost is seats x a configurable per-seat price, since the
API returns no price. Everything degrades to empty on 401/403/404.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, cache: Any, seat_cost: float) -> None:
        self._token = token
        self._cache = cache
        self._seat_cost = seat_cost
        self._client = httpx.Client(timeout=60)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def copilot_summary(self, org: str) -> dict[str, Any]:
        """Return {org, seats, cost, acceptance_pct} for one org. Empty on error."""
        cache_key = f"ghcopilot:{org.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        out = {"org": org, "seats": 0, "cost": 0.0, "acceptance_pct": 0.0}
        if not self._token:
            return out
        try:
            resp = self._client.get(f"{_API}/orgs/{org}/copilot/billing", headers=self._headers())
            resp.raise_for_status()
            breakdown = resp.json().get("seat_breakdown", {})
            seats = int(breakdown.get("total") or 0)
            out["seats"] = seats
            out["cost"] = round(seats * self._seat_cost, 2)
        except Exception as exc:  # pragma: no cover - permission/no-copilot
            logger.info("copilot billing for org %s unavailable: %s", org, exc)
            self._cache.set(cache_key, out)
            return out
        out["acceptance_pct"] = self._acceptance(org)
        self._cache.set(cache_key, out)
        return out

    def _acceptance(self, org: str) -> float:
        """Average code-completion acceptance % across the metrics window."""
        try:
            resp = self._client.get(f"{_API}/orgs/{org}/copilot/metrics", headers=self._headers())
            resp.raise_for_status()
            days = resp.json()
        except Exception as exc:  # pragma: no cover - metrics not enabled
            logger.info("copilot metrics for org %s unavailable: %s", org, exc)
            return 0.0
        suggested = accepted = 0
        for day in days if isinstance(days, list) else []:
            comp = (day or {}).get("copilot_ide_code_completions") or {}
            for editor in comp.get("editors", []):
                for model in editor.get("models", []):
                    for lang in model.get("languages", []):
                        suggested += int(lang.get("total_code_suggestions") or 0)
                        accepted += int(lang.get("total_code_acceptances") or 0)
        return round(accepted / suggested * 100, 1) if suggested else 0.0
