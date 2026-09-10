"""FastAPI application factory for the Affiliate FinOps backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import affiliates, analytics, costs, health, macc


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Affiliate FinOps API",
        version="0.1.0",
        description="Centralized affiliate cost, MACC consumption, and license data.",
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
