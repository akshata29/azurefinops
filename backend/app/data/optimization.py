"""Slice A — reservations & savings plans (rate optimization) demo data."""
from __future__ import annotations

from app.data.demo import build_affiliates, _rng
from app.data.resources import build_resources
from app.models import RateOptimization, ReservationRecommendation, SavingsByService

# Services eligible for reservations / savings plans.
_ELIGIBLE = {
    "Virtual Machines": "1 year",
    "Azure SQL Database": "3 years",
    "Cosmos DB": "1 year",
    "Azure Data Explorer": "1 year",
    "App Service": "1 year",
    "PostgreSQL Flexible": "3 years",
}


def build_rate_optimization(affiliate_id: str | None) -> RateOptimization:
    affiliates = build_affiliates()
    if affiliate_id:
        affiliates = [a for a in affiliates if a.affiliate_id == affiliate_id]

    by_service: dict[str, float] = {}
    recommendations: list[ReservationRecommendation] = []
    commitment = 0.0
    savings_to_date = 0.0
    plan_count = 0

    for aff in affiliates:
        r = _rng(f"rate:{aff.affiliate_id}")
        resources = build_resources(aff.affiliate_id)
        svc_spend: dict[str, float] = {}
        for rc in resources:
            if rc.service_name in _ELIGIBLE:
                svc_spend[rc.service_name] = svc_spend.get(rc.service_name, 0.0) + rc.cost
        for service, spend in svc_spend.items():
            savings_pct = r.uniform(0.18, 0.42)
            monthly_savings = spend * savings_pct
            by_service[service] = by_service.get(service, 0.0) + monthly_savings
            recommendations.append(
                ReservationRecommendation(
                    affiliate_id=aff.affiliate_id,
                    service=service,
                    sku=f"{service.split()[0]}-reserved",
                    term=_ELIGIBLE[service],
                    recommended_quantity=r.randint(1, 20),
                    monthly_savings=round(monthly_savings, 2),
                    savings_pct=round(savings_pct * 100, 1),
                )
            )
        commitment += sum(svc_spend.values()) * r.uniform(0.4, 0.8)
        savings_to_date += sum(svc_spend.values()) * r.uniform(0.1, 0.3)
        plan_count += r.randint(0, 3)

    by_service_list = sorted(
        (SavingsByService(service=s, potential_savings=round(v, 2)) for s, v in by_service.items()),
        key=lambda x: x.potential_savings,
        reverse=True,
    )
    recommendations.sort(key=lambda x: x.monthly_savings, reverse=True)

    return RateOptimization(
        potential_reservation_savings=round(sum(by_service.values()), 2),
        savings_plan_commitment=round(commitment, 2),
        savings_to_date=round(savings_to_date, 2),
        active_savings_plans=plan_count,
        by_service=by_service_list,
        recommendations=recommendations[:25],
    )
