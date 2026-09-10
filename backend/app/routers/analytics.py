"""Rate optimization (reservations & savings plans), prepayment, offer mix, hierarchy, AI, TCO."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import provider_dep
from app.models import (
    AffiliateHierarchy,
    AiConsumption,
    OfferMixSlice,
    PrepaymentSummary,
    RateOptimization,
    TcoSummary,
)
from app.services.provider import DataProvider

router = APIRouter(tags=["analytics"])


@router.get("/rate-optimization", response_model=RateOptimization)
def rate_optimization(
    affiliate_id: str | None = None, provider: DataProvider = Depends(provider_dep)
) -> RateOptimization:
    return provider.rate_optimization(affiliate_id)


@router.get("/prepayment", response_model=PrepaymentSummary)
def prepayment(provider: DataProvider = Depends(provider_dep)) -> PrepaymentSummary:
    return provider.prepayment()


@router.get("/offer-mix", response_model=list[OfferMixSlice])
def offer_mix(provider: DataProvider = Depends(provider_dep)) -> list[OfferMixSlice]:
    return provider.offer_mix()


@router.get("/affiliates/{affiliate_id}/hierarchy", response_model=AffiliateHierarchy)
def hierarchy(affiliate_id: str, provider: DataProvider = Depends(provider_dep)) -> AffiliateHierarchy:
    h = provider.hierarchy(affiliate_id)
    if h is None:
        raise HTTPException(status_code=404, detail=f"Affiliate {affiliate_id} not found")
    return h


@router.get("/ai-consumption", response_model=AiConsumption)
def ai_consumption(
    affiliate_id: str | None = None, provider: DataProvider = Depends(provider_dep)
) -> AiConsumption:
    return provider.ai_consumption(affiliate_id)


@router.get("/tco", response_model=TcoSummary)
def tco(affiliate_id: str | None = None, provider: DataProvider = Depends(provider_dep)) -> TcoSummary:
    return provider.tco(affiliate_id)
