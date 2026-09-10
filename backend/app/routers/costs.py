"""Cost + license endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import provider_dep
from app.models import CostSummary, License
from app.services.provider import DataProvider

router = APIRouter(tags=["costs"])


@router.get("/costs", response_model=CostSummary)
def cost_summary(
    affiliate_id: str | None = None, provider: DataProvider = Depends(provider_dep)
) -> CostSummary:
    return provider.cost_summary(affiliate_id)


@router.get("/licenses", response_model=list[License])
def licenses(
    affiliate_id: str | None = None, provider: DataProvider = Depends(provider_dep)
) -> list[License]:
    return provider.licenses(affiliate_id)
