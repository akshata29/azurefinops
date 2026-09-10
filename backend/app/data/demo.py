"""Deterministic demo-data generator so the dashboard runs without Azure.

Generates a realistic set of affiliates with MACC commitments, monthly cost
trends, drawdown events, and license assignments. Seeded for stable output.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from app.models import (
    Affiliate,
    AgreementType,
    CostByService,
    CostPoint,
    CostSummary,
    License,
    MaccBalance,
    MaccDetail,
    MaccEvent,
    MaccStatus,
    MaccTrendPoint,
    OnboardingStatus,
)

_SEED = 20260909
_TODAY = date(2026, 9, 9)

_AFFILIATE_NAMES = [
    "Contoso Retail", "Fabrikam Health", "Northwind Logistics", "Adventure Works",
    "Tailspin Media", "Wingtip Finance", "Proseware Energy", "Litware Manufacturing",
    "Fourth Coffee", "Graphic Design Institute", "Coho Vineyard", "Lucerne Publishing",
]

_SERVICES = [
    "Virtual Machines", "Storage", "Azure SQL", "App Service", "AKS",
    "Networking", "Cognitive Services", "Data Explorer", "Monitor", "Key Vault",
]


def _rng(key: str) -> random.Random:
    return random.Random(f"{_SEED}:{key}")


def _month_labels(n: int) -> list[str]:
    labels: list[str] = []
    y, m = _TODAY.year, _TODAY.month
    for _ in range(n):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(labels))


def build_affiliates() -> list[Affiliate]:
    out: list[Affiliate] = []
    for i, name in enumerate(_AFFILIATE_NAMES):
        r = _rng(f"aff:{name}")
        agreement = AgreementType.EA if i % 3 else AgreementType.MCA
        status = OnboardingStatus.ACTIVE
        if i == len(_AFFILIATE_NAMES) - 1:
            status = OnboardingStatus.ONBOARDING
        elif i == len(_AFFILIATE_NAMES) - 2:
            status = OnboardingStatus.ERROR
        out.append(
            Affiliate(
                affiliate_id=f"aff-{i + 1:03d}",
                name=name,
                tenant_id=f"{r.randint(10000000, 99999999):08x}-aaaa-bbbb-cccc-{r.randint(100000000000, 999999999999):012x}",
                agreement_type=agreement,
                billing_account=f"{r.randint(1000000, 9999999)}",
                billing_profile=(None if agreement == AgreementType.EA else f"{r.randint(1000, 9999)}-{r.randint(1000, 9999)}-{r.randint(1000, 9999)}"),
                status=status,
                onboarded_on=_TODAY - timedelta(days=r.randint(30, 400)),
                last_data_refresh=(None if status == OnboardingStatus.ONBOARDING else _TODAY - timedelta(days=r.randint(0, 2))),
            )
        )
    return out


def _commitment_for(affiliate_id: str) -> float:
    r = _rng(f"commit:{affiliate_id}")
    return float(r.choice([500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000]))


def build_macc_balance(aff: Affiliate) -> MaccBalance:
    r = _rng(f"macc:{aff.affiliate_id}")
    commitment = _commitment_for(aff.affiliate_id)
    start = date(2025, 1, 1)
    end = date(2027, 12, 31)
    term_days = (end - start).days
    elapsed = max(0, (_TODAY - start).days)
    days_remaining = max(0, (end - _TODAY).days)
    # Burn between 55% and 130% of the linear pace, to create on/off-track mixes.
    pace = r.uniform(0.55, 1.30)
    consumed = min(commitment, commitment * (elapsed / term_days) * pace)
    consumed = round(consumed, 2)
    remaining = round(commitment - consumed, 2)
    pct = round(consumed / commitment * 100, 1)

    monthly_burn = consumed / max(1, elapsed / 30.0)
    months_to_exhaust = remaining / monthly_burn if monthly_burn > 0 else 999
    projected = _TODAY + timedelta(days=int(months_to_exhaust * 30))
    on_track = projected >= end  # exhausting AFTER end means you may under-consume; before means over-consume
    # "On track" here = trending to consume the full commitment close to end date.
    linear_expected_pct = elapsed / term_days * 100
    on_track = abs(pct - linear_expected_pct) <= 12

    return MaccBalance(
        affiliate_id=aff.affiliate_id,
        affiliate_name=aff.name,
        commitment_amount=commitment,
        remaining_balance=remaining,
        consumed_amount=consumed,
        percent_consumed=pct,
        start_date=start,
        end_date=end,
        days_remaining=days_remaining,
        status=MaccStatus.ACTIVE,
        projected_exhaustion_date=projected if projected <= end else None,
        on_track=on_track,
    )


def build_macc_detail(aff: Affiliate) -> MaccDetail:
    balance = build_macc_balance(aff)
    months = _month_labels(12)
    consumed_total = balance.consumed_amount
    # Distribute cumulative consumption smoothly across the last 12 months.
    r = _rng(f"trend:{aff.affiliate_id}")
    weights = [r.uniform(0.7, 1.3) for _ in months]
    wsum = sum(weights)
    trend: list[MaccTrendPoint] = []
    events: list[MaccEvent] = []
    cumulative = max(0.0, consumed_total - consumed_total * 0.9)
    remaining = balance.commitment_amount - cumulative
    for label, w in zip(months, weights):
        step = consumed_total * 0.9 * (w / wsum)
        cumulative += step
        remaining = round(balance.commitment_amount - cumulative, 2)
        trend.append(
            MaccTrendPoint(month=label, remaining_balance=remaining, consumed_cumulative=round(cumulative, 2))
        )
        events.append(
            MaccEvent(
                affiliate_id=aff.affiliate_id,
                event_date=date(int(label[:4]), int(label[5:]), 1),
                description=f"Invoiced Azure consumption — {label}",
                charges=round(step, 2),
                remaining_after=remaining,
            )
        )
    return MaccDetail(balance=balance, trend=trend, events=list(reversed(events)))


def build_cost_summary(affiliate_id: str | None) -> CostSummary:
    affiliates = build_affiliates()
    if affiliate_id:
        affiliates = [a for a in affiliates if a.affiliate_id == affiliate_id]
    months = _month_labels(12)
    trend: list[CostPoint] = []
    service_totals: dict[str, float] = {s: 0.0 for s in _SERVICES}
    for aff in affiliates:
        r = _rng(f"cost:{aff.affiliate_id}")
        base = r.uniform(20_000, 90_000)
        for idx, label in enumerate(months):
            seasonal = 1 + 0.25 * (idx / len(months)) + r.uniform(-0.08, 0.08)
            cost = round(base * seasonal, 2)
            trend.append(
                CostPoint(
                    month=label,
                    affiliate_id=aff.affiliate_id,
                    cost=cost,
                    amortized_cost=round(cost * r.uniform(0.9, 1.05), 2),
                )
            )
        for s in _SERVICES:
            service_totals[s] += base * r.uniform(0.3, 1.5)

    # Aggregate trend by month across affiliates.
    by_month: dict[str, float] = {}
    by_month_amort: dict[str, float] = {}
    for p in trend:
        by_month[p.month] = by_month.get(p.month, 0.0) + p.cost
        by_month_amort[p.month] = by_month_amort.get(p.month, 0.0) + p.amortized_cost
    agg_trend = [
        CostPoint(month=m, affiliate_id=affiliate_id or "ALL", cost=round(by_month[m], 2), amortized_cost=round(by_month_amort[m], 2))
        for m in months
    ]
    mtd = agg_trend[-1].cost
    last = agg_trend[-2].cost if len(agg_trend) > 1 else mtd
    mom = round((mtd - last) / last * 100, 1) if last else 0.0
    by_service = sorted(
        (CostByService(service=s, cost=round(v, 2)) for s, v in service_totals.items()),
        key=lambda x: x.cost,
        reverse=True,
    )
    return CostSummary(
        total_cost_mtd=round(mtd, 2),
        total_cost_last_month=round(last, 2),
        mom_change_pct=mom,
        trend=agg_trend,
        by_service=by_service,
    )


def build_licenses(affiliate_id: str | None) -> list[License]:
    affiliates = build_affiliates()
    if affiliate_id:
        affiliates = [a for a in affiliates if a.affiliate_id == affiliate_id]
    products = [
        ("Microsoft 365 E5", "M365-E5", 57.0),
        ("Microsoft 365 E3", "M365-E3", 36.0),
        ("Power BI Premium", "PBI-PREM", 20.0),
        ("Visual Studio Enterprise", "VS-ENT", 250.0),
        ("GitHub Enterprise", "GH-ENT", 21.0),
    ]
    out: list[License] = []
    for aff in affiliates:
        r = _rng(f"lic:{aff.affiliate_id}")
        for name, sku, unit in r.sample(products, k=r.randint(2, len(products))):
            assigned = r.randint(50, 2000)
            out.append(
                License(
                    affiliate_id=aff.affiliate_id,
                    product=name,
                    sku=sku,
                    assigned=assigned,
                    consumed=int(assigned * r.uniform(0.6, 0.99)),
                    unit_cost=unit,
                    renewal_date=_TODAY + timedelta(days=r.randint(30, 365)),
                )
            )
    return out
