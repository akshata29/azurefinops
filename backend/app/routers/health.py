"""Health + meta endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    s = get_settings()
    return {
        "status": "ok",
        "mode": "mock" if s.use_mock else "live",
        "data_source": "synthetic" if s.use_mock else s.data_backend,
    }
