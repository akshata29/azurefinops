"""Shared FastAPI dependencies."""
from __future__ import annotations

from app.config import get_settings
from app.services.provider import DataProvider, get_provider


def provider_dep() -> DataProvider:
    return get_provider(get_settings())
