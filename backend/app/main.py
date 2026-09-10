"""FastAPI application factory for the Affiliate FinOps backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import affiliates, analytics, costs, health, macc

logger = logging.getLogger(__name__)


def _log_cost_throttle_status() -> None:
    """Surface any persisted Cost Management throttle cooldown at startup so a
    restart makes it obvious we're waiting out Azure's budget, not stuck."""
    settings = get_settings()
    if settings.use_mock:
        return
    try:
        from app.services.provider import get_provider

        client = getattr(get_provider(settings), "client", None)
        remaining = client.throttle_cooldown_remaining() if client else 0.0
        if remaining > 0:
            logger.warning(
                "Cost Management throttle cooldown active: %.0fs remaining — "
                "serving cached/stale history until it clears (no API calls).",
                remaining,
            )
        else:
            logger.info("Cost Management throttle: no active cooldown.")
    except Exception as exc:  # pragma: no cover - never block startup
        logger.debug("cost throttle status check skipped: %s", exc)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _log_cost_throttle_status()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Affiliate FinOps API",
        version="0.1.0",
        description="Centralized affiliate cost, MACC consumption, and license data.",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(affiliates.router, prefix=api_prefix)
    app.include_router(macc.router, prefix=api_prefix)
    app.include_router(costs.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)

    return app


app = create_app()
