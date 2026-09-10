"""Affiliate registry + portfolio summary endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import provider_dep
from app.models import Affiliate, AffiliateCostDetail, PortfolioSummary, ResourceCost
from app.services.provider import DataProvider

router = APIRouter(tags=["affiliates"])


@router.get("/summary", response_model=PortfolioSummary)
def portfolio_summary(provider: DataProvider = Depends(provider_dep)) -> PortfolioSummary:
    return provider.portfolio_summary()


@router.get("/affiliates", response_model=list[Affiliate])
def list_affiliates(provider: DataProvider = Depends(provider_dep)) -> list[Affiliate]:
    return provider.affiliates()


@router.get("/affiliates/{affiliate_id}/breakdown", response_model=AffiliateCostDetail)
def affiliate_breakdown(
    affiliate_id: str, provider: DataProvider = Depends(provider_dep)
) -> AffiliateCostDetail:
    detail = provider.affiliate_breakdown(affiliate_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Affiliate {affiliate_id} not found")
    return detail


@router.get("/affiliates/{affiliate_id}/resources", response_model=list[ResourceCost])
def affiliate_resources(
    affiliate_id: str, provider: DataProvider = Depends(provider_dep)
) -> list[ResourceCost]:
    return provider.affiliate_resources(affiliate_id)
