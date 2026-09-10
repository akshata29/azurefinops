"""Azure Cost Management client — pulls *real* cost data for a subscription.

This is the live-data engine used when ``USE_MOCK=false``. It talks to the ARM
Cost Management Query API directly (over HTTPS with ``httpx``) so we don't need a
FinOps hub / ADX cluster to see real numbers for a plain Azure subscription.

Design notes
------------
* **Auth** — a bearer token for ``https://management.azure.com``. If a client id +
  secret (+ tenant) are configured we use client-credentials; otherwise we fall
  back to :class:`azure.identity.DefaultAzureCredential` so ``az login`` just works.
* **Throttling** — Cost Management is aggressively rate-limited (HTTP 429). Every
  call goes through :meth:`_post`/``_get`` with exponential backoff that honours
  ``Retry-After`` / ``x-ms-ratelimit-microsoft.costmanagement-*`` headers.
* **History** — the Query API caps a custom range at ~1 year, so we chunk the
  requested window into <=365-day slices and merge, walking backwards until the
  data runs out.
* **Caching** — an in-process TTL cache keeps the dashboard responsive and keeps
  us well under the API's request budget.

Everything returns plain dicts/lists; mapping to Pydantic models lives in
``provider.py`` so this module stays a thin, testable data layer.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_ARM = "https://management.azure.com"
_SCOPE = "https://management.azure.com/.default"
_CM_API = "2023-11-01"
_SUBS_API = "2022-12-01"
_MAX_WINDOW_DAYS = 364  # Query API rejects custom ranges wider than ~1 year.
# The binding real-world limit is the per-client *request count* (clienttype),
# not QPU (which has huge headroom). So use FEWER, larger requests: 6 months of
# data per call (6 QPU) — well under the 12-QPU/10s bucket, but a third as many
# requests as per-month. 13 months of history is then ~3 calls per series.
_MAX_WINDOW_MONTHS = 6
# QPU budget used to derive a safe request cap (kept just under the real 12/60).
_QPU_PER_10S = 11
_QPU_PER_MIN = 55
_MAX_RETRIES = 9
_BACKOFF_CAP = 90.0
# On a 429 we back off hard and only a few times — each throttled retry itself
# burns QPU, so aggressive retrying deepens the penalty instead of escaping it.
_MAX_THROTTLE_RETRIES = 3
_THROTTLE_MIN_COOLDOWN = 20.0  # floor when the server gives no explicit hint
# Adaptive pacing: when a request-count quota (e.g. clienttype-requests) reports
# this few remaining, pause proactively so we stop *before* it 429s.
_LOW_QUOTA_THRESHOLD = 1
_LOW_QUOTA_COOLDOWN = 20.0


class _ThrottledError(RuntimeError):
    """Raised when Cost Management stays throttled after the retry budget."""


# --------------------------------------------------------------------------- #
# Small TTL cache
# --------------------------------------------------------------------------- #
@dataclass
class _CacheEntry:
    value: Any
    expires_at: float  # wall-clock epoch seconds (survives process restart)


class _TTLCache:
    """Thread-safe TTL cache that persists to disk.

    Persisting matters because uvicorn ``--reload`` (and any restart) would
    otherwise drop every cached result and re-fire the whole Cost Management
    query budget cold — the exact cause of sustained 429 storms. Entries carry a
    wall-clock expiry so they remain valid across restarts.
    """

    def __init__(self, ttl_seconds: int, path: str | None = None) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, _CacheEntry] = {}
        self._lock = threading.RLock()
        self._path = path
        self._load()

    def _load(self) -> None:
        if not self._path:
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return
        now = time.time()
        for key, item in (raw or {}).items():
            try:
                exp = float(item["expires_at"])
            except (KeyError, TypeError, ValueError):
                continue
            if exp > now:
                self._data[key] = _CacheEntry(item["value"], exp)
        if self._data:
            logger.info("Loaded %d cached Cost Management results from %s", len(self._data), self._path)

    def _flush(self) -> None:
        if not self._path:
            return
        try:
            payload = {k: {"value": e.value, "expires_at": e.expires_at} for k, e in self._data.items()}
            tmp = f"{self._path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self._path)
        except (OSError, TypeError, ValueError) as exc:  # non-serialisable / disk issue
            logger.debug("cost cache flush skipped: %s", exc)

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = _CacheEntry(value, time.time() + self._ttl)
            self._flush()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._flush()


# --------------------------------------------------------------------------- #
# Simple request-rate limiter for the Query API
# --------------------------------------------------------------------------- #
class _RateLimiter:
    """Paces Cost Management Query-API calls to two independent throttles.

    1. **QPU** (per docs): 1 QPU per month queried; 12/10s and 60/min per tenant.
       We derive a request cap from the window size so QPU is never exceeded.
    2. **Request count** (e.g. ``clienttype-requests``): a small, undocumented
       per-client bucket. Its exact size isn't published, so we react to the
       ``remaining`` header and honour the server's ``Retry-After`` on a 429.

    When throttled we open a persisted cooldown so a restart or the frontend's
    polling can't keep a quota saturated — it drains, then traffic resumes.
    """

    _COOLDOWN_CAP = 600.0  # escalating fallback ceiling (10 min)

    def __init__(self, path: str | None = None) -> None:
        self._events: deque[float] = deque()  # request timestamps (monotonic)
        self._lock = threading.Lock()
        self._path = path
        self._consecutive = 0  # consecutive throttle trips (drives escalation)
        # Cap requests/window from the QPU budget: each request costs
        # (_MAX_WINDOW_MONTHS) QPU, so allow floor(budget / months) per window.
        per_10s = max(1, int(_QPU_PER_10S // _MAX_WINDOW_MONTHS))
        per_min = max(1, int(_QPU_PER_MIN // _MAX_WINDOW_MONTHS))
        self._limits: tuple[tuple[float, int], ...] = ((10.0, per_10s), (60.0, per_min))
        # Cooldown is tracked in *wall-clock* epoch seconds and persisted, so a
        # process restart still honours an Azure-side throttle window.
        self._cooldown_epoch = self._load_cooldown()
        remaining = self._cooldown_epoch - time.time()
        if remaining > 0:
            logger.warning(
                "Cost Management is in a throttle cooldown for %.0fs more (persisted from a prior run); "
                "requests will serve cached data instead of re-triggering 429s.",
                remaining,
            )

    def _load_cooldown(self) -> float:
        if not self._path:
            return 0.0
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return float(json.load(fh).get("cooldown_until", 0.0))
        except (OSError, ValueError, TypeError, AttributeError):
            return 0.0

    def _save_cooldown(self) -> None:
        if not self._path:
            return
        try:
            tmp = f"{self._path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"cooldown_until": self._cooldown_epoch}, fh)
            os.replace(tmp, self._path)
        except (OSError, TypeError, ValueError):  # pragma: no cover
            pass

    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown_epoch - time.time())

    def acquire(self) -> None:
        """Block until a request slot is free. Raises :class:`_ThrottledError`
        immediately if a cooldown is active (fail fast so callers serve stale and
        no traffic hits Azure while the windows drain)."""
        if self.cooldown_remaining() > 0:
            raise _ThrottledError("Cost Management cooling down")
        while True:
            if self.cooldown_remaining() > 0:
                raise _ThrottledError("Cost Management cooling down")
            with self._lock:
                now = time.monotonic()
                horizon = now - self._limits[-1][0]
                while self._events and self._events[0] < horizon:
                    self._events.popleft()
                wait = 0.0
                for window, limit in self._limits:
                    recent = [ts for ts in self._events if ts > now - window]
                    if len(recent) >= limit:
                        wait = max(wait, recent[0] + window - now)
                if wait <= 0:
                    self._events.append(now)
                    return
            time.sleep(min(max(wait, 0.05), 30.0))

    def trip(self, delay: float, escalate: bool = False) -> float:
        """Open/extend the cooldown after a 429.

        When the server gave an explicit Retry-After (``escalate=False``) we
        honour that value exactly, per the docs. Only when there's no server
        hint (``escalate=True``) do we apply a doubling fallback so we don't
        hammer a silent throttle. Returns the effective cooldown seconds."""
        with self._lock:
            if escalate:
                self._consecutive += 1
                delay = min(self._COOLDOWN_CAP, max(0.0, float(delay)) * (2 ** (self._consecutive - 1)))
            else:
                self._consecutive = 0  # server told us exactly; no escalation
                delay = min(self._COOLDOWN_CAP, max(0.0, float(delay)))
            target = time.time() + delay
            if target > self._cooldown_epoch:
                self._cooldown_epoch = target
                self._save_cooldown()
            return delay

    def recover(self) -> None:
        """A call succeeded — clear the escalation and any cooldown."""
        with self._lock:
            if self._consecutive or self._cooldown_epoch:
                self._consecutive = 0
                self._cooldown_epoch = 0.0
                self._save_cooldown()

    def wait_out_cooldown(self, poll: float = 5.0) -> None:
        """Block until any active cooldown clears (for batch/CLI use)."""
        while True:
            remaining = self.cooldown_remaining()
            if remaining <= 0:
                return
            time.sleep(min(remaining, poll))


class _InFlight:
    """Barrier for single-flight request de-duplication."""

    __slots__ = ("event", "result", "error")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None
        self.error: Exception | None = None


# --------------------------------------------------------------------------- #
# Permanent monthly history store
# --------------------------------------------------------------------------- #
class _MonthlyHistoryStore:
    """Permanent, per-subscription store of *closed* monthly cost data.

    Closed months are immutable in Cost Management — Azure only revises the
    current (and briefly the prior) month as late usage settles. So once a
    closed month is fetched we persist it here forever and never re-query it;
    only the open month is refreshed. This turns a steady-state dashboard load
    from ~13 QPU/query into ~1–2 QPU. One JSON file per subscription; each file
    maps ``series -> {"YYYY-MM": value}``.
    """

    def __init__(self, root: str) -> None:
        self._root = root
        self._lock = threading.Lock()
        try:
            os.makedirs(root, exist_ok=True)
        except OSError as exc:  # pragma: no cover - disk/permission
            logger.warning("cost history dir unavailable (%s): %s", root, exc)

    def _path(self, subscription_id: str) -> str:
        safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in subscription_id) or "sub"
        return os.path.join(self._root, f"{safe}.json")

    def _load(self, subscription_id: str) -> dict[str, Any]:
        try:
            with open(self._path(subscription_id), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get_series(self, subscription_id: str, series: str) -> dict[str, Any]:
        return dict(self._load(subscription_id).get(series, {}))

    def put_series(self, subscription_id: str, series: str, month_map: dict[str, Any]) -> None:
        if not month_map:
            return
        with self._lock:
            data = self._load(subscription_id)
            bucket = data.setdefault(series, {})
            if not isinstance(bucket, dict):
                bucket = {}
                data[series] = bucket
            bucket.update(month_map)
            path = self._path(subscription_id)
            try:
                tmp = f"{path}.{os.getpid()}.tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                os.replace(tmp, path)
            except (OSError, TypeError, ValueError) as exc:  # pragma: no cover
                logger.warning("cost history flush failed for %s: %s", subscription_id, exc)


# --------------------------------------------------------------------------- #
# Token provider
# --------------------------------------------------------------------------- #
@dataclass
class _TokenProvider:
    """Acquires ARM tokens, caching a credential + token per tenant.

    Multi-tenant onboarding uses one token per affiliate tenant. With a
    multi-tenant app registration (client id/secret) we can mint a token for any
    tenant that has consented; otherwise DefaultAzureCredential is scoped to the
    given tenant (requires the signed-in identity to have access there).
    """

    settings: Settings
    _creds: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _tokens: dict[str, tuple[str, float]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _tenant_key(self, tenant_id: str | None) -> str:
        return (tenant_id or self.settings.azure_tenant_id or "_default_").lower()

    def _build_credential(self, tenant_id: str | None) -> Any:
        s = self.settings
        effective_tenant = tenant_id or s.azure_tenant_id
        if s.azure_client_id and s.azure_client_secret and effective_tenant:
            from azure.identity import ClientSecretCredential

            logger.info("Azure auth: client-credentials (tenant=%s)", effective_tenant)
            return ClientSecretCredential(
                tenant_id=effective_tenant,
                client_id=s.azure_client_id,
                client_secret=s.azure_client_secret,
            )
        from azure.identity import DefaultAzureCredential

        logger.info("Azure auth: DefaultAzureCredential (tenant=%s)", effective_tenant or "signed-in")
        kwargs: dict[str, Any] = {"exclude_interactive_browser_credential": True}
        if effective_tenant:
            kwargs["tenant_id"] = effective_tenant
        return DefaultAzureCredential(**kwargs)

    def token(self, tenant_id: str | None = None, scope: str = _SCOPE) -> str:
        key = f"{self._tenant_key(tenant_id)}|{scope}"
        with self._lock:
            now = time.time()
            cached = self._tokens.get(key)
            if cached and now < cached[1] - 120:
                return cached[0]
            cred_key = self._tenant_key(tenant_id)
            cred = self._creds.get(cred_key)
            if cred is None:
                cred = self._build_credential(tenant_id)
                self._creds[cred_key] = cred
            access = cred.get_token(scope)
            self._tokens[key] = (access.token, float(access.expires_on))
            return access.token


# --------------------------------------------------------------------------- #
# Cost Management client
# --------------------------------------------------------------------------- #
class AzureCostClient:
    """Thin wrapper over ARM subscription + Cost Management Query APIs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tokens = _TokenProvider(settings)
        cache_path = os.path.join(tempfile.gettempdir(), "azurefinops_cost_cache.json")
        self._cache = _TTLCache(settings.cache_ttl_seconds, path=cache_path)
        hist_root = settings.cost_history_dir or str(Path(__file__).resolve().parents[2] / "data" / "cost_history")
        self._history = _MonthlyHistoryStore(hist_root)
        cooldown_path = os.path.join(tempfile.gettempdir(), "azurefinops_cost_cooldown.json")
        self._limiter = _RateLimiter(path=cooldown_path)
        self._settle_days = int(getattr(settings, "cost_settle_days", 5))
        self._inflight: dict[str, _InFlight] = {}
        self._inflight_lock = threading.Lock()
        self._client = httpx.Client(timeout=120)

    @property
    def token_provider(self) -> "_TokenProvider":
        """Shared token provider so sibling clients (Graph) reuse credentials."""
        return self._tokens

    @property
    def cache(self) -> "_TTLCache":
        """Shared TTL cache so sibling clients reuse the same request budget."""
        return self._cache

    def throttle_cooldown_remaining(self) -> float:
        """Seconds remaining on the persisted Cost Management throttle cooldown."""
        return self._limiter.cooldown_remaining()

    # -- HTTP helpers ------------------------------------------------------- #
    def _headers(self, tenant_id: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens.token(tenant_id)}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _server_retry_after(cls, resp: httpx.Response) -> float | None:
        """The server's explicit back-off hint (seconds), or None if absent.

        Cost Management throttles on several independent quotas (qpu, clienttype,
        entity, tenant) and returns a *per-quota* retry-after header, e.g.
        ``x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after``. We
        take the largest hint present so we satisfy the binding quota, and fall
        back to the generic ``Retry-After``.
        """
        delays: list[float] = []
        for key, value in resp.headers.items():
            kl = key.lower()
            if "costmanagement" in kl and kl.endswith("-retry-after"):
                try:
                    delays.append(float(value))
                except (ValueError, TypeError):
                    pass
        raw = resp.headers.get("Retry-After")
        if raw:
            try:
                delays.append(float(raw))
            except ValueError:
                pass
        ms = resp.headers.get("retry-after-ms")
        if ms:
            try:
                delays.append(float(ms) / 1000.0)
            except ValueError:
                pass
        return max(delays) if delays else None

    @staticmethod
    def _min_remaining_requests(resp: httpx.Response) -> int | None:
        """Smallest remaining count across Cost Management request-count quotas
        (clienttype/entity/tenant), parsed from the ``...remaining...requests``
        headers whose value looks like ``DefaultQuota:3``. Lets us slow down
        *before* a quota hits zero. QPU (a different unit) is ignored here.
        """
        mins: list[int] = []
        for key, value in resp.headers.items():
            kl = key.lower()
            if "ratelimit-remaining-microsoft.costmanagement" in kl and kl.endswith("-requests"):
                for part in str(value).split(","):
                    seg = part.split(":")[-1].strip()
                    try:
                        mins.append(int(seg))
                    except ValueError:
                        pass
        return min(mins) if mins else None

    @staticmethod
    def _fallback_delay(attempt: int) -> float:
        """Backoff used only when the server sends no Retry-After header."""
        import random

        base = min(_BACKOFF_CAP, 4.0 * (2.0 ** attempt))
        return base + random.uniform(0, 3.0)

    @staticmethod
    def _rate_limit_headers(resp: httpx.Response) -> dict[str, str]:
        """Every throttling/ratelimit header on the response, for diagnostics."""
        return {
            k: v
            for k, v in resp.headers.items()
            if "ratelimit" in k.lower() or "retry-after" in k.lower()
        }

    @staticmethod
    def _sf_key(method: str, url: str, body: dict | None) -> str:
        blob = json.dumps(body, sort_keys=True, default=str) if body else ""
        return hashlib.sha1(f"{method}\n{url}\n{blob}".encode("utf-8")).hexdigest()

    def _request(self, method: str, url: str, body: dict | None = None, tenant_id: str | None = None, block: bool = False) -> dict[str, Any]:
        """Single-flight wrapper: concurrent identical calls share one round-trip.

        Repeated dashboard polls of the same endpoint would otherwise each fire
        the same Cost Management query while the first is still in flight,
        multiplying load against the throttle. Here the first caller ("leader")
        performs the request; any concurrent caller with the same
        method+url+body waits and reuses its result.

        ``block=True`` (used by the pre-warm backfill) waits out any throttle
        cooldown and retries instead of failing fast, so it actually downloads.
        """
        key = self._sf_key(method, url, body)
        with self._inflight_lock:
            flight = self._inflight.get(key)
            leader = flight is None
            if leader:
                flight = _InFlight()
                self._inflight[key] = flight
        assert flight is not None
        if not leader:
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            return flight.result
        try:
            result = self._do_request(method, url, body, tenant_id, block=block)
            flight.result = result
            return result
        except Exception as exc:
            flight.error = exc
            raise
        finally:
            flight.event.set()
            with self._inflight_lock:
                self._inflight.pop(key, None)

    def _do_request(self, method: str, url: str, body: dict | None = None, tenant_id: str | None = None, block: bool = False) -> dict[str, Any]:
        # Only the Cost Management **Query API** (POST /query) is rate-limited on
        # QPU; GET reads (subscriptions, recommendations, MACC lots, …) use
        # separate, far more generous ARM limits, so they bypass the pacer.
        is_query = method.upper() == "POST"
        last_exc: Exception | None = None
        throttle_hits = 0
        attempt = 0
        while attempt < _MAX_RETRIES:
            if is_query:
                if block:
                    # Backfill mode: wait out any cooldown instead of failing fast.
                    self._limiter.wait_out_cooldown()
                try:
                    self._limiter.acquire()  # paces to <=10/10s; raises _ThrottledError while cooling down
                except _ThrottledError:
                    if block:
                        self._limiter.wait_out_cooldown()
                        continue
                    raise
            try:
                resp = self._client.request(method, url, headers=self._headers(tenant_id), json=body)
            except httpx.HTTPError as exc:  # transient network issue
                last_exc = exc
                time.sleep(min(30.0, 2.0 ** attempt))
                attempt += 1
                continue
            if resp.status_code in (429, 503, 500):
                server_delay = self._server_retry_after(resp)
                if not is_query:
                    # ARM throttle on a GET — plain bounded backoff, no cooldown.
                    delay = max(server_delay if server_delay is not None else self._fallback_delay(attempt), 1.0)
                    if not block and attempt + 1 >= _MAX_THROTTLE_RETRIES:
                        raise _ThrottledError(f"Cost Management throttled: {url}")
                    time.sleep(min(delay, _BACKOFF_CAP))
                    attempt += 1
                    continue
                throttle_hits += 1
                # Surface the actual rate-limit headers so we can see *which*
                # limit is at zero (QPU remaining, subscription reads/writes, or
                # the per-service bucket) and the exact Retry-After.
                logger.warning(
                    "Cost Management POST %s; rate-limit headers: %s",
                    resp.status_code, self._rate_limit_headers(resp) or "(none provided)",
                )
                # Honour the server's Retry-After exactly (docs: "back off for the
                # time specified in this header"). Only escalate when it's absent.
                if server_delay is not None:
                    delay = self._limiter.trip(server_delay, escalate=False)
                else:
                    delay = self._limiter.trip(max(self._fallback_delay(throttle_hits), _THROTTLE_MIN_COOLDOWN), escalate=True)
                if block:
                    # Backfill: wait out the cooldown and retry this same month.
                    logger.info(
                        "Cost Management POST throttled (%s); waiting %.0fs (server hint=%s) then retrying (attempt %d).",
                        resp.status_code, delay, f"{server_delay:.0f}s" if server_delay is not None else "none", throttle_hits,
                    )
                    self._limiter.wait_out_cooldown()
                    attempt += 1
                    continue
                logger.warning(
                    "Cost Management POST throttled (%s); cooling down %.0fs and serving cached/stale data.",
                    resp.status_code, delay,
                )
                # Fail fast — no in-request retries. The next request after the
                # cooldown probes once and either recovers or backs off further.
                raise _ThrottledError(f"Cost Management throttled: {url}")
            resp.raise_for_status()
            if is_query:
                # Adaptive, header-driven pacing (docs: "the rate-limited response
                # will provide the necessary information to adjust your calls").
                # Clear any prior throttle, then if a request-count quota is about
                # to run out, pause *before* it 429s so we stop fighting it.
                self._limiter.recover()
                remaining = self._min_remaining_requests(resp)
                if remaining is not None and remaining <= _LOW_QUOTA_THRESHOLD:
                    self._limiter.trip(_LOW_QUOTA_COOLDOWN, escalate=False)
                    logger.info(
                        "Cost Management request quota low (remaining=%d); pausing %.0fs to let it refill.",
                        remaining, _LOW_QUOTA_COOLDOWN,
                    )
            if not resp.content:
                return {}
            return resp.json()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Cost Management request failed after {_MAX_RETRIES} retries: {url}")

    # -- Subscriptions ------------------------------------------------------ #
    def list_subscriptions(self) -> list[dict[str, Any]]:
        """Return subscriptions the identity can read (or the configured subset)."""
        configured = self.settings.subscription_id_list
        cache_key = f"subs:{','.join(configured) or 'all'}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if configured:
            subs = [self._get_subscription(sid) for sid in configured]
            subs = [s for s in subs if s]
        else:
            url = f"{_ARM}/subscriptions?api-version={_SUBS_API}"
            subs = []
            while url:
                data = self._request("GET", url)
                for item in data.get("value", []):
                    subs.append(self._sub_row(item))
                url = data.get("nextLink") or ""
        self._cache.set(cache_key, subs)
        return subs

    def _get_subscription(self, subscription_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        url = f"{_ARM}/subscriptions/{subscription_id}?api-version={_SUBS_API}"
        try:
            return self._sub_row(self._request("GET", url, tenant_id=tenant_id))
        except httpx.HTTPStatusError as exc:  # pragma: no cover - permissions
            logger.warning("Cannot read subscription %s: %s", subscription_id, exc)
            return None

    @staticmethod
    def _sub_row(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "subscription_id": item.get("subscriptionId") or "",
            "display_name": item.get("displayName") or item.get("subscriptionId") or "Subscription",
            "state": item.get("state") or "Enabled",
            "tenant_id": item.get("tenantId") or "",
        }

    # -- Cost queries ------------------------------------------------------- #
    def _query_scope(self, subscription_id: str) -> str:
        return f"{_ARM}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version={_CM_API}"

    def subscription_meta(self, subscription_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        """Read a single subscription's metadata (cached)."""
        cache_key = f"submeta:{subscription_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        meta = self._get_subscription(subscription_id, tenant_id)
        if meta is not None:
            self._cache.set(cache_key, meta)
        return meta

    def _run_query(self, subscription_id: str, body: dict[str, Any], tenant_id: str | None = None, block: bool = False) -> list[dict[str, Any]]:
        """Execute a query (following nextLink pagination) into list-of-dict rows."""
        url = self._query_scope(subscription_id)
        rows: list[dict[str, Any]] = []
        next_body: dict | None = body
        next_url = url
        while next_url:
            data = self._request("POST", next_url, next_body, tenant_id=tenant_id, block=block)
            props = data.get("properties", {})
            columns = [c.get("name") for c in props.get("columns", [])]
            for raw in props.get("rows", []):
                rows.append(dict(zip(columns, raw)))
            next_url = props.get("nextLink") or ""
            next_body = None  # nextLink carries the query; re-post with empty body
        return rows

    def _windows(self, months: int) -> list[tuple[str, str]]:
        """Split the requested history into <=1-year ISO windows (oldest first)."""
        today = datetime.now(timezone.utc).date()
        start = _add_months(today.replace(day=1), -(months - 1))
        windows: list[tuple[str, str]] = []
        cursor = start
        while cursor <= today:
            win_end = min(today, cursor + timedelta(days=_MAX_WINDOW_DAYS))
            windows.append((_iso(cursor), _iso(win_end, end_of_day=True)))
            cursor = win_end + timedelta(days=1)
        return windows

    @staticmethod
    def _recent_months(months: int) -> list[str]:
        """The last ``months`` calendar months as 'YYYY-MM', oldest first."""
        first = datetime.now(timezone.utc).date().replace(day=1)
        labels = []
        for i in range(months):
            d = _add_months(first, -i)
            labels.append(f"{d.year:04d}-{d.month:02d}")
        return list(reversed(labels))

    @staticmethod
    def _open_months(settle_days: int = 5) -> set[str]:
        """Months that are still mutable and must be re-fetched.

        Always the current month; plus the just-closed prior month during the
        first ``settle_days`` of a new month, while late usage is still landing.
        This keeps steady-state refreshes at ~1 QPU/query most of the time.
        """
        today = datetime.now(timezone.utc).date()
        first = today.replace(day=1)
        months = {f"{first.year:04d}-{first.month:02d}"}
        if today.day <= max(0, settle_days):
            prev = _add_months(first, -1)
            months.add(f"{prev.year:04d}-{prev.month:02d}")
        return months

    def _month_windows(self, start_label: str, end: date) -> list[tuple[str, str]]:
        """Month-aligned query windows (<= _MAX_WINDOW_MONTHS each) from the first
        of ``start_label`` through ``end``. Aligning to month boundaries keeps
        every month wholly inside one window, so a window that succeeds can be
        persisted immediately without splitting a month across a throttle."""
        cursor = date(int(start_label[:4]), int(start_label[5:7]), 1)
        end_month_first = end.replace(day=1)
        windows: list[tuple[str, str]] = []
        while cursor <= end_month_first:
            last_first = min(_add_months(cursor, _MAX_WINDOW_MONTHS - 1), end_month_first)
            win_end = min(_add_months(last_first, 1) - timedelta(days=1), end)
            windows.append((_iso(cursor), _iso(win_end, end_of_day=True)))
            cursor = _add_months(last_first, 1)
        return windows

    def _incremental_months(
        self,
        subscription_id: str,
        series: str,
        months: int,
        build_body,
        parse_rows,
        tenant_id: str | None,
        block: bool = False,
    ) -> dict[str, Any]:
        """Return ``{month: value}`` for the requested window, fetching only the
        months not already persisted plus the open month(s), and persisting
        newly-closed months permanently — **per window**, so a window that
        succeeds is never discarded when a later one throttles.

        ``build_body(frm, to)`` produces the query body for a date window;
        ``parse_rows(rows)`` reduces one month's raw rows into a stored value.
        ``block=True`` (pre-warm) waits out cooldowns and retries until it
        actually downloads, rather than serving stale.
        """
        needed = self._recent_months(months)
        open_months = self._open_months(self._settle_days)
        stored = self._history.get_series(subscription_id, series)
        to_fetch = [m for m in needed if m not in stored or m in open_months]
        # Dashboard path: if we're already cooling down, don't block request
        # threads — serve the closed months we have. (Backfill ignores this and
        # waits the cooldown out instead.)
        if to_fetch and not block and self._limiter.cooldown_remaining() > 0:
            logger.info(
                "Cost Management cooling down %.0fs; serving %d stored months for %s/%s.",
                self._limiter.cooldown_remaining(), len(stored), subscription_id, series,
            )
            return {m: stored[m] for m in needed if m in stored}

        fetched: dict[str, Any] = {}
        if to_fetch:
            start_label = min(to_fetch)
            end = datetime.now(timezone.utc).date()
            throttled = False
            for frm, to in self._month_windows(start_label, end):
                try:
                    raw_by_month: dict[str, list[dict[str, Any]]] = {}
                    for row in self._run_query(subscription_id, build_body(frm, to), tenant_id=tenant_id, block=block):
                        month = _month_key(row)
                        if month:
                            raw_by_month.setdefault(month, []).append(row)
                except _ThrottledError:
                    # Non-block dashboard call hit the throttle — stop, but keep
                    # everything already persisted by earlier windows.
                    throttled = True
                    break
                window_values = {m: parse_rows(rows) for m, rows in raw_by_month.items()}
                fetched.update(window_values)
                # Persist this window's CLOSED months immediately (durable progress).
                closed = {m: v for m, v in window_values.items() if m not in open_months}
                if closed:
                    self._history.put_series(subscription_id, series, closed)
                    stored = {**stored, **closed}
            if throttled:
                logger.info(
                    "Serving cached history for %s/%s (%d stored months) while throttled.",
                    subscription_id, series, len(stored),
                )

        out: dict[str, Any] = {}
        for month in needed:
            if month in open_months and month in fetched:
                out[month] = fetched[month]  # freshest value for the open month
            elif month in stored:
                out[month] = stored[month]
            elif month in fetched:
                out[month] = fetched[month]
        return out

    def monthly_totals(
        self, subscription_id: str, months: int, amortized: bool = False, tenant_id: str | None = None, block: bool = False
    ) -> list[dict[str, Any]]:
        """Monthly cost totals for the subscription (actual or amortized)."""
        kind = "AmortizedCost" if amortized else "ActualCost"
        cache_key = f"monthly:{subscription_id}:{months}:{kind}"
        if not block:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def build_body(frm: str, to: str) -> dict[str, Any]:
            return {
                "type": kind,
                "timeframe": "Custom",
                "timePeriod": {"from": frm, "to": to},
                "dataset": {
                    "granularity": "Monthly",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"},
                        "totalCostUSD": {"name": "CostUSD", "function": "Sum"},
                    },
                },
            }

        def parse_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
            cost = cost_usd = 0.0
            currency = "USD"
            for row in rows:
                cost += _num(row.get("Cost"))
                cost_usd += _num(row.get("CostUSD"))
                currency = row.get("Currency") or currency
            return {"cost": cost, "cost_usd": cost_usd, "currency": currency}

        by_month = self._incremental_months(
            subscription_id, f"monthly:{kind}", months, build_body, parse_rows, tenant_id, block=block
        )
        result = [dict(month=m, **by_month[m]) for m in sorted(by_month)]
        if result:  # never cache an empty (throttled) result — it would mask real data for the TTL
            self._cache.set(cache_key, result)
        return result

    def resource_costs(self, subscription_id: str, months: int, tenant_id: str | None = None, block: bool = False) -> list[dict[str, Any]]:
        """Resource-level costs (whole window) grouped by ResourceId + ServiceName."""
        cache_key = f"resources:{subscription_id}:{months}"
        if not block:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def build_body(frm: str, to: str) -> dict[str, Any]:
            return {
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {"from": frm, "to": to},
                "dataset": {
                    "granularity": "Monthly",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"},
                        "totalCostUSD": {"name": "CostUSD", "function": "Sum"},
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ResourceId"},
                        {"type": "Dimension", "name": "ServiceName"},
                    ],
                },
            }

        def parse_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            agg: dict[tuple[str, str], dict[str, Any]] = {}
            for row in rows:
                resource_id = (row.get("ResourceId") or "").lower()
                service = row.get("ServiceName") or "Other"
                bucket = agg.setdefault(
                    (resource_id, service),
                    {"resource_id": resource_id, "service_name": service, "cost": 0.0, "cost_usd": 0.0, "currency": "USD"},
                )
                bucket["cost"] += _num(row.get("Cost"))
                bucket["cost_usd"] += _num(row.get("CostUSD"))
                bucket["currency"] = row.get("Currency") or bucket["currency"]
            return list(agg.values())

        by_month = self._incremental_months(
            subscription_id, "resources", months, build_body, parse_rows, tenant_id, block=block
        )
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for items in by_month.values():
            for it in items:
                key = (it["resource_id"], it["service_name"])
                bucket = merged.setdefault(
                    key,
                    {"resource_id": it["resource_id"], "service_name": it["service_name"], "cost": 0.0, "cost_usd": 0.0, "currency": "USD"},
                )
                bucket["cost"] += _num(it.get("cost"))
                bucket["cost_usd"] += _num(it.get("cost_usd"))
                bucket["currency"] = it.get("currency") or bucket["currency"]
        result = list(merged.values())
        if result:
            self._cache.set(cache_key, result)
        return result

    def dimension_totals(
        self, subscription_id: str, dimension: str, months: int, tenant_id: str | None = None, block: bool = False
    ) -> list[dict[str, Any]]:
        """Whole-window totals grouped by a single dimension (e.g. PricingModel)."""
        cache_key = f"dim:{subscription_id}:{dimension}:{months}"
        if not block:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        def build_body(frm: str, to: str) -> dict[str, Any]:
            return {
                "type": "ActualCost",
                "timeframe": "Custom",
                "timePeriod": {"from": frm, "to": to},
                "dataset": {
                    "granularity": "Monthly",
                    "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                    "grouping": [{"type": "Dimension", "name": dimension}],
                },
            }

        def parse_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            agg: dict[str, dict[str, Any]] = {}
            for row in rows:
                key = row.get(dimension) or "Unknown"
                bucket = agg.setdefault(key, {"key": key, "cost": 0.0, "currency": "USD"})
                bucket["cost"] += _num(row.get("Cost"))
                bucket["currency"] = row.get("Currency") or bucket["currency"]
            return list(agg.values())

        by_month = self._incremental_months(
            subscription_id, f"dim:{dimension}", months, build_body, parse_rows, tenant_id, block=block
        )
        merged: dict[str, dict[str, Any]] = {}
        for items in by_month.values():
            for it in items:
                bucket = merged.setdefault(it["key"], {"key": it["key"], "cost": 0.0, "currency": "USD"})
                bucket["cost"] += _num(it.get("cost"))
                bucket["currency"] = it.get("currency") or bucket["currency"]
        result = sorted(merged.values(), key=lambda r: r["cost"], reverse=True)
        if result:
            self._cache.set(cache_key, result)
        return result

    # -- Reservation & savings-plan recommendations ------------------------ #
    def reservation_recommendations(
        self, subscription_id: str, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Azure reservation (RI) purchase recommendations, normalised.

        Handles both the ``legacy`` and ``modern`` recommendation shapes (amounts
        are either plain numbers or ``{value, currency}`` objects) and normalises
        savings to a ~monthly figure based on the look-back period.
        """
        cache_key = f"resrec:{subscription_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = (
            f"{_ARM}/subscriptions/{subscription_id}/providers/Microsoft.Consumption"
            f"/reservationRecommendations?api-version=2023-05-01"
        )
        recs: list[dict[str, Any]] = []
        try:
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                for item in data.get("value", []):
                    rec = _normalize_reservation(item)
                    if rec:
                        recs.append(rec)
                url = data.get("nextLink") or ""
        except httpx.HTTPError as exc:  # pragma: no cover - permission/transient
            logger.warning("reservation_recommendations %s failed: %s", subscription_id, exc)
        self._cache.set(cache_key, recs)
        return recs

    def savings_plan_recommendations(
        self, subscription_id: str, tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Aggregate savings-plan (benefit) recommendation totals, best-effort.

        Returns ``{"commitment": float, "savings": float, "currency": str}``.
        Empty/zero when the subscription has no benefit recommendations or the
        API is unavailable.
        """
        cache_key = f"splan:{subscription_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = (
            f"{_ARM}/subscriptions/{subscription_id}/providers/Microsoft.CostManagement"
            f"/benefitRecommendations?api-version=2024-08-01"
            f"&$filter=properties/lookBackPeriod eq 'Last30Days' and properties/term eq 'P1Y'"
        )
        out = {"commitment": 0.0, "savings": 0.0, "currency": "USD"}
        try:
            data = self._request("GET", url, tenant_id=tenant_id)
            best = 0.0
            for item in data.get("value", []):
                props = item.get("properties", {})
                # Shape: recommendationDetails.overallSavingsPlanRecommendation / usage
                details = props.get("recommendationDetails") or props
                commitment = _num(
                    (details.get("commitmentAmount") if isinstance(details, dict) else None)
                    or props.get("commitmentAmount")
                )
                savings = _num(
                    (details.get("savingsAmount") if isinstance(details, dict) else None)
                    or props.get("savingsAmount")
                )
                if savings >= best:
                    best = savings
                    out = {"commitment": commitment, "savings": savings, "currency": props.get("currencyCode", "USD")}
        except httpx.HTTPError as exc:  # pragma: no cover - permission/transient/preview
            logger.info("savings_plan_recommendations %s unavailable: %s", subscription_id, exc)
        self._cache.set(cache_key, out)
        return out

    # -- Existing commitments (reservations + savings plans) --------------- #
    def commitment_inventory(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Count existing reservation orders + savings plans and their commitment.

        Uses tenant-level ARM endpoints; returns
        ``{"reservations": int, "savings_plans": int, "commitment": float}``.
        Best-effort — zeros when none exist or the identity lacks access.
        """
        cache_key = f"commitinv:{self._tokens._tenant_key(tenant_id)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        out = {"reservations": 0, "savings_plans": 0, "commitment": 0.0}
        # Reservation orders.
        try:
            url = f"{_ARM}/providers/Microsoft.Capacity/reservationOrders?api-version=2022-11-01"
            count = 0
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                for item in data.get("value", []):
                    props = item.get("properties", {})
                    state = str(props.get("provisioningState") or props.get("displayProvisioningState") or "").lower()
                    if state in ("", "succeeded", "active"):
                        count += 1
                url = data.get("nextLink") or ""
            out["reservations"] = count
        except Exception as exc:  # pragma: no cover
            logger.info("reservationOrders unavailable: %s", exc)
        # Savings plans (billing benefits).
        try:
            url = f"{_ARM}/providers/Microsoft.BillingBenefits/savingsPlans?api-version=2024-11-01-preview"
            count, commitment = 0, 0.0
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                for item in data.get("value", []):
                    props = item.get("properties", {})
                    if str(props.get("provisioningState") or "").lower() in ("", "succeeded", "active"):
                        count += 1
                        commitment += _num((props.get("commitment") or {}).get("amount"))
                url = data.get("nextLink") or ""
            out["savings_plans"] = count
            out["commitment"] = round(commitment, 2)
        except Exception as exc:  # pragma: no cover
            logger.info("savingsPlans unavailable: %s", exc)
        self._cache.set(cache_key, out)
        return out

    def realized_commitment_value(self, subscription_id: str, months: int, tenant_id: str | None = None) -> float:
        """Amortized reservation + savings-plan spend in the window (value realized)."""
        cache_key = f"realized:{subscription_id}:{months}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        total = 0.0
        for frm, to in self._windows(months):
            body = {
                "type": "AmortizedCost",
                "timeframe": "Custom",
                "timePeriod": {"from": frm, "to": to},
                "dataset": {
                    "granularity": "None",
                    "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                    "grouping": [{"type": "Dimension", "name": "PricingModel"}],
                },
            }
            try:
                for row in self._run_query(subscription_id, body, tenant_id=tenant_id):
                    model = str(row.get("PricingModel") or "").lower()
                    if model in ("reservation", "savingsplan", "savings plan"):
                        total += _num(row.get("Cost"))
            except Exception as exc:  # pragma: no cover
                logger.info("realized_commitment_value %s unavailable: %s", subscription_id, exc)
        result = round(total, 2)
        self._cache.set(cache_key, result)
        return result

    # -- MACC (consumption commitment) lots + drawdown events -------------- #
    def macc_lots(self, billing_account: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """MACC commitment lots for a billing account (Microsoft.Consumption/lots)."""
        cache_key = f"maccltos:{billing_account}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = (
            f"{_ARM}/providers/Microsoft.Billing/billingAccounts/{billing_account}"
            f"/providers/Microsoft.Consumption/lots?api-version=2021-05-01"
            f"&$filter=source eq 'ConsumptionCommitment'"
        )
        lots: list[dict[str, Any]] = []
        try:
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                lots.extend(data.get("value", []))
                url = data.get("nextLink") or ""
        except Exception as exc:  # pragma: no cover - permission/no-MACC
            logger.info("macc_lots %s unavailable: %s", billing_account, exc)
        self._cache.set(cache_key, lots)
        return lots

    def macc_events(
        self, billing_account: str, start_date: str, end_date: str, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """MACC drawdown events for a billing account (Microsoft.Consumption/events)."""
        cache_key = f"maccev:{billing_account}:{start_date}:{end_date}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = (
            f"{_ARM}/providers/Microsoft.Billing/billingAccounts/{billing_account}"
            f"/providers/Microsoft.Consumption/events?api-version=2021-05-01"
            f"&startDate={start_date}&endDate={end_date}"
            f"&$filter=lotSource eq 'ConsumptionCommitment'"
        )
        events: list[dict[str, Any]] = []
        try:
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                events.extend(data.get("value", []))
                url = data.get("nextLink") or ""
        except Exception as exc:  # pragma: no cover - permission/no-MACC
            logger.info("macc_events %s unavailable: %s", billing_account, exc)
        self._cache.set(cache_key, events)
        return events

    def monitor_token_totals(
        self, resource_id: str, months: int, tenant_id: str | None = None
    ) -> dict[str, float]:
        """Monthly token totals for an Azure OpenAI resource via Azure Monitor.

        Returns ``{'YYYY-MM': tokens}``. Empty when the metric is unavailable.
        Platform metrics retain ~93 days, so older months may be absent.
        """
        cache_key = f"tokens:{resource_id}:{months}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        # Monitor retains platform metrics ~93 days.
        end = datetime.now(timezone.utc).date()
        start = max(_add_months(end.replace(day=1), -(months - 1)), end - timedelta(days=90))
        url = (
            f"{_ARM}{resource_id}/providers/microsoft.insights/metrics"
            f"?api-version=2023-10-01&metricnames=TokenTransaction&aggregation=Total"
            f"&interval=P1D&timespan={start.isoformat()}T00:00:00Z/{end.isoformat()}T00:00:00Z"
        )
        monthly: dict[str, float] = {}
        try:
            data = self._request("GET", url, tenant_id=tenant_id)
            for metric in data.get("value", []):
                for series in metric.get("timeseries", []):
                    for point in series.get("data", []):
                        ts = str(point.get("timeStamp") or "")
                        total = _num(point.get("total"))
                        if ts and total:
                            monthly[ts[:7]] = monthly.get(ts[:7], 0.0) + total
        except Exception as exc:  # pragma: no cover - metric/permission
            logger.info("monitor tokens for %s unavailable: %s", resource_id, exc)
        self._cache.set(cache_key, monthly)
        return monthly

    def list_deployments(self, resource_id: str, tenant_id: str | None = None) -> dict[str, str]:
        """Map ``deployment name -> model name`` for a Cognitive Services account.

        Uses the ARM deployments API (not QPU-limited). Empty when unavailable.
        """
        cache_key = f"deployments:{resource_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        url = f"{_ARM}{resource_id}/deployments?api-version=2023-05-01"
        mapping: dict[str, str] = {}
        try:
            while url:
                data = self._request("GET", url, tenant_id=tenant_id)
                for item in data.get("value", []):
                    name = item.get("name") or ""
                    model = ((item.get("properties") or {}).get("model") or {}).get("name") or ""
                    if name:
                        mapping[name] = model
                url = data.get("nextLink") or ""
        except Exception as exc:  # pragma: no cover - permission/transient
            logger.info("deployments list for %s unavailable: %s", resource_id, exc)
        self._cache.set(cache_key, mapping)
        return mapping

    def monitor_deployment_tpm(
        self, resource_id: str, hours: int = 24, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Per-deployment tokens-per-minute over the last ``hours``.

        Reads the Azure Monitor ``TokenTransaction`` metric (total processed
        inference tokens) at 1-minute granularity, split by the
        ``ModelDeploymentName`` dimension — the supported way to monitor each
        deployment individually. Returns one entry per deployment:
        ``{deployment, total_tokens, avg_tpm, peak_tpm, active_minutes}``.
        """
        cache_key = f"tpm:{resource_id}:{hours}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        end = datetime.now(timezone.utc).replace(microsecond=0)
        start = end - timedelta(hours=hours)
        params = {
            "api-version": "2023-10-01",
            "metricnames": "TokenTransaction",
            "aggregation": "Total",
            "interval": "PT1M",
            "$filter": "ModelDeploymentName eq '*'",
            "timespan": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        }
        url = f"{_ARM}{resource_id}/providers/microsoft.insights/metrics?{urlencode(params)}"
        out: list[dict[str, Any]] = []
        try:
            data = self._request("GET", url, tenant_id=tenant_id)
            for metric in data.get("value", []):
                for series in metric.get("timeseries", []):
                    name = ""
                    for mv in series.get("metadatavalues", []):
                        if str((mv.get("name") or {}).get("value", "")).lower() == "modeldeploymentname":
                            name = str(mv.get("value") or "")
                    per_min = [
                        _num(p.get("total"))
                        for p in series.get("data", [])
                        if p.get("total") is not None
                    ]
                    active = [v for v in per_min if v > 0]
                    if not active:
                        continue
                    out.append(
                        {
                            "deployment": name or "(unnamed)",
                            "total_tokens": round(sum(active), 0),
                            "avg_tpm": round(sum(active) / len(active), 1),
                            "peak_tpm": round(max(active), 0),
                            "active_minutes": len(active),
                        }
                    )
        except Exception as exc:  # pragma: no cover - metric/permission
            logger.info("deployment TPM for %s unavailable: %s", resource_id, exc)
        out.sort(key=lambda d: d["peak_tpm"], reverse=True)
        self._cache.set(cache_key, out)
        return out

    def clear_cache(self) -> None:
        self._cache.clear()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _num(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _amount(value: Any) -> tuple[float, str]:
    """Read a cost amount that may be a plain number or {value, currency}."""
    if isinstance(value, dict):
        return _num(value.get("value")), str(value.get("currency") or "USD")
    return _num(value), "USD"


_TERM_LABEL = {"P1M": "1 month", "P1Y": "1 year", "P3Y": "3 years"}
_LOOKBACK_DAYS = {"Last7Days": 7, "Last30Days": 30, "Last60Days": 60}


def _normalize_reservation(item: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise a legacy/modern reservationRecommendation into flat fields."""
    props = item.get("properties", {})
    net, currency = _amount(props.get("netSavings"))
    cost_no_ri, cur2 = _amount(props.get("costWithNoReservedInstances"))
    currency = currency if currency != "USD" else cur2
    # Normalise savings from the look-back period to ~monthly.
    days = _LOOKBACK_DAYS.get(str(props.get("lookBackPeriod")), 30)
    scale = 30.0 / days if days else 1.0
    monthly_savings = round(net * scale, 2)
    monthly_cost = cost_no_ri * scale
    qty = props.get("recommendedQuantity")
    if qty is None:
        qty = props.get("recommendedQuantityNormalized")
    return {
        "resource_type": props.get("resourceType") or item.get("sku") or "Compute",
        "sku": props.get("skuName") or props.get("sku") or item.get("sku") or "",
        "term": _TERM_LABEL.get(str(props.get("term")), str(props.get("term") or "1 year")),
        "scope": props.get("scope") or "Shared",
        "recommended_quantity": int(round(_num(qty))),
        "monthly_savings": monthly_savings,
        "savings_pct": round(net / cost_no_ri * 100, 1) if cost_no_ri else 0.0,
        "monthly_cost": round(monthly_cost, 2),
        "currency": currency,
    }


def _iso(d: date, end_of_day: bool = False) -> str:
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{d.isoformat()}{suffix}"


def _add_months(d: date, delta: int) -> date:
    month_index = d.year * 12 + (d.month - 1) + delta
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _month_key(row: dict[str, Any]) -> str | None:
    """Normalise the date column (BillingMonth / UsageDate) to 'YYYY-MM'."""
    raw = row.get("BillingMonth") or row.get("UsageDate") or row.get("Date")
    if raw is None:
        return None
    text = str(raw)
    if "T" in text:  # ISO datetime, e.g. 2025-08-01T00:00:00
        return text[:7]
    digits = text.replace("-", "")
    if len(digits) >= 6 and digits[:8].isdigit():
        return f"{digits[:4]}-{digits[4:6]}"
    return None

