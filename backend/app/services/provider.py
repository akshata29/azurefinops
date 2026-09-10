"""Data provider abstraction.

`MockDataProvider` serves the deterministic demo dataset. `LiveDataProvider`
queries the real central store (ADX/Fabric/storage) plus the MACC puller. The
active provider is chosen from settings (USE_MOCK).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.config import Settings
from app.data import demo
from app.data import resources as resource_demo
from app.data import optimization as opt_demo
from app.data import billing as billing_demo
from app.data import ai as ai_demo
from app.data import tco as tco_demo
from app.models import (
    Affiliate,
    AffiliateCostDetail,
    AffiliateHierarchy,
    AiConsumption,
    CostSummary,
    License,
    MaccBalance,
    MaccDetail,
    OfferMixSlice,
    PortfolioSummary,
    PrepaymentSummary,
    RateOptimization,
    ResourceCost,
    TcoSummary,
)


class DataProvider(Protocol):
    def affiliates(self) -> list[Affiliate]: ...
    def macc_balances(self) -> list[MaccBalance]: ...
    def macc_detail(self, affiliate_id: str) -> MaccDetail | None: ...
    def cost_summary(self, affiliate_id: str | None) -> CostSummary: ...
    def licenses(self, affiliate_id: str | None) -> list[License]: ...
    def portfolio_summary(self) -> PortfolioSummary: ...
    def affiliate_breakdown(self, affiliate_id: str) -> AffiliateCostDetail | None: ...
    def affiliate_resources(self, affiliate_id: str) -> list[ResourceCost]: ...
    def rate_optimization(self, affiliate_id: str | None) -> RateOptimization: ...
    def prepayment(self) -> PrepaymentSummary: ...
    def offer_mix(self) -> list[OfferMixSlice]: ...
    def hierarchy(self, affiliate_id: str) -> AffiliateHierarchy | None: ...
    def ai_consumption(self, affiliate_id: str | None) -> AiConsumption: ...
    def tco(self, affiliate_id: str | None) -> TcoSummary: ...


def _portfolio_from(balances: list[MaccBalance], affiliates: list[Affiliate], cost_mtd: float) -> PortfolioSummary:
    total_commit = sum(b.commitment_amount for b in balances)
    total_remaining = sum(b.remaining_balance for b in balances)
    total_consumed = sum(b.consumed_amount for b in balances)
    at_risk = sum(1 for b in balances if not b.on_track)
    return PortfolioSummary(
        affiliate_count=len(affiliates),
        active_count=sum(1 for a in affiliates if a.status.value == "Active"),
        total_commitment=round(total_commit, 2),
        total_remaining=round(total_remaining, 2),
        total_consumed=round(total_consumed, 2),
        percent_consumed=round(total_consumed / total_commit * 100, 1) if total_commit else 0.0,
        total_cost_mtd=round(cost_mtd, 2),
        at_risk_count=at_risk,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


class MockDataProvider:
    """Deterministic demo data — no Azure required."""

    def affiliates(self) -> list[Affiliate]:
        return demo.build_affiliates()

    def macc_balances(self) -> list[MaccBalance]:
        return [demo.build_macc_balance(a) for a in demo.build_affiliates()]

    def macc_detail(self, affiliate_id: str) -> MaccDetail | None:
        for a in demo.build_affiliates():
            if a.affiliate_id == affiliate_id:
                return demo.build_macc_detail(a)
        return None

    def cost_summary(self, affiliate_id: str | None) -> CostSummary:
        return demo.build_cost_summary(affiliate_id)

    def licenses(self, affiliate_id: str | None) -> list[License]:
        return demo.build_licenses(affiliate_id)

    def portfolio_summary(self) -> PortfolioSummary:
        return _portfolio_from(self.macc_balances(), self.affiliates(), self.cost_summary(None).total_cost_mtd)

    def affiliate_breakdown(self, affiliate_id: str) -> AffiliateCostDetail | None:
        if not any(a.affiliate_id == affiliate_id for a in demo.build_affiliates()):
            return None
        return resource_demo.build_breakdown(affiliate_id)

    def affiliate_resources(self, affiliate_id: str) -> list[ResourceCost]:
        return resource_demo.build_resources(affiliate_id)

    def rate_optimization(self, affiliate_id: str | None) -> RateOptimization:
        return opt_demo.build_rate_optimization(affiliate_id)

    def prepayment(self) -> PrepaymentSummary:
        return billing_demo.build_prepayment()

    def offer_mix(self) -> list[OfferMixSlice]:
        return billing_demo.build_offer_mix()

    def hierarchy(self, affiliate_id: str) -> AffiliateHierarchy | None:
        return billing_demo.build_hierarchy(affiliate_id)

    def ai_consumption(self, affiliate_id: str | None) -> AiConsumption:
        return ai_demo.build_ai_consumption(affiliate_id)

    def tco(self, affiliate_id: str | None) -> TcoSummary:
        return tco_demo.build_tco(affiliate_id)


class LiveDataProvider:
    """Live provider — queries ADX/storage and the MACC puller.

    Wired for the real environment. Query bodies are intentionally left as
    integration points; the shapes mirror MockDataProvider so the API contract
    is identical regardless of source.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Lazy imports so demo mode needs no Azure SDKs installed at runtime.
        from app.services.macc_puller import MaccPuller  # noqa: WPS433

        self.macc = MaccPuller(settings)

    def affiliates(self) -> list[Affiliate]:  # pragma: no cover - integration
        raise NotImplementedError("Query the affiliate registry (Cosmos/SQL/ADX) here.")

    def macc_balances(self) -> list[MaccBalance]:  # pragma: no cover - integration
        raise NotImplementedError("Read MaccBalance table (ADX) populated by MaccPuller.")

    def macc_detail(self, affiliate_id: str) -> MaccDetail | None:  # pragma: no cover
        raise NotImplementedError("Read MaccBalance + FactMaccEvent for the affiliate.")

    def cost_summary(self, affiliate_id: str | None) -> CostSummary:  # pragma: no cover
        raise NotImplementedError("Query FOCUS Costs table in ADX/Fabric.")

    def licenses(self, affiliate_id: str | None) -> list[License]:  # pragma: no cover
        raise NotImplementedError("Query DimLicense reference table.")

    def portfolio_summary(self) -> PortfolioSummary:  # pragma: no cover
        raise NotImplementedError("Aggregate over MaccBalance + Costs in ADX.")

    def affiliate_breakdown(self, affiliate_id: str) -> AffiliateCostDetail | None:  # pragma: no cover
        raise NotImplementedError("Group FOCUS Costs by ServiceCategory/Service/ResourceType/ResourceId in ADX.")

    def affiliate_resources(self, affiliate_id: str) -> list[ResourceCost]:  # pragma: no cover
        raise NotImplementedError("Query resource-level FOCUS rows for the affiliate in ADX.")

    def rate_optimization(self, affiliate_id: str | None) -> RateOptimization:  # pragma: no cover
        raise NotImplementedError("Read ReservationRecommendations + savings plan datasets (FinOps hubs).")

    def prepayment(self) -> PrepaymentSummary:  # pragma: no cover
        raise NotImplementedError("Aggregate MACC lots + Azure prepayment balances.")

    def offer_mix(self) -> list[OfferMixSlice]:  # pragma: no cover
        raise NotImplementedError("Group FOCUS invoiced usage by PricingModel/offer type.")

    def hierarchy(self, affiliate_id: str) -> AffiliateHierarchy | None:  # pragma: no cover
        raise NotImplementedError("Group FOCUS by BillingProfile/InvoiceSection/Subscription/RG/Resource.")

    def ai_consumption(self, affiliate_id: str | None) -> AiConsumption:  # pragma: no cover
        raise NotImplementedError("Combine FOCUS AI meters + Azure Monitor tokens + GitHub/Graph Copilot APIs.")

    def tco(self, affiliate_id: str | None) -> TcoSummary:  # pragma: no cover
        raise NotImplementedError("Union Azure FOCUS cost + license feed + external Copilot spend.")


def get_provider(settings: Settings) -> DataProvider:
    if settings.use_mock:
        return MockDataProvider()
    return LiveDataProvider(settings)
