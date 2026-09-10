"""MACC endpoints — balances across affiliates and per-affiliate detail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import provider_dep
from app.models import MaccBalance, MaccDetail
from app.services.provider import DataProvider

router = APIRouter(prefix="/macc", tags=["macc"])


@router.get("/balances", response_model=list[MaccBalance])
def macc_balances(provider: DataProvider = Depends(provider_dep)) -> list[MaccBalance]:
    return provider.macc_balances()


@router.get("/{affiliate_id}", response_model=MaccDetail)
def macc_detail(affiliate_id: str, provider: DataProvider = Depends(provider_dep)) -> MaccDetail:
    detail = provider.macc_detail(affiliate_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Affiliate {affiliate_id} not found")
    return detail
