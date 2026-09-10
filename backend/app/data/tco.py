"""Slice E — Total Cost of Ownership roll-up (Azure + licenses + external Copilot).

Azure cost (FOCUS) already includes Azure OpenAI/Foundry/Security/Fabric Copilot, so
those are NOT double-counted. Only *external* license spend (M365/GitHub/VS/PBI billed
outside Azure) and external Copilot seats (GitHub/M365) are added on top.
"""
from __future__ import annotations

from app.data.ai import build_ai_consumption
from app.data.demo import build_cost_summary, build_licenses, _month_labels
from app.models import TcoSourceSlice, TcoSummary, TcoTrendPoint


def build_tco(affiliate_id: str | None) -> TcoSummary:
    costs = build_cost_summary(affiliate_id)
    azure = costs.total_cost_mtd

    licenses = build_licenses(affiliate_id)
    license_monthly = round(sum(l.assigned * l.unit_cost for l in licenses), 2)

    ai = build_ai_consumption(affiliate_id)
    external_copilot = round(
        sum(r.cost for r in ai.rows if r.source in ("GitHub Copilot", "M365 Copilot")), 2
    )

    total = round(azure + license_monthly + external_copilot, 2)

    by_source = [
        TcoSourceSlice(source="Azure", cost=round(azure, 2)),
        TcoSourceSlice(source="Licenses", cost=license_monthly),
        TcoSourceSlice(source="Copilot (external)", cost=external_copilot),
    ]

    # Build a 12-month stacked trend using the Azure trend shape.
    months = _month_labels(12)
    azure_by_month = {p.month: p.cost for p in costs.trend}
    trend: list[TcoTrendPoint] = []
    for m in months:
        a = azure_by_month.get(m, azure)
        trend.append(
            TcoTrendPoint(
                month=m,
                azure=round(a, 2),
                licenses=license_monthly,
                copilot_external=external_copilot,
            )
        )

    return TcoSummary(
        total=total,
        azure_cost=round(azure, 2),
        license_cost=license_monthly,
        external_copilot_cost=external_copilot,
        by_source=by_source,
        trend=trend,
    )
