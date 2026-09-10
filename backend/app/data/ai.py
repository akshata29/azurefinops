"""Slice D — AI & Copilot consumption (Azure OpenAI/Foundry, GitHub, M365)."""
from __future__ import annotations

from app.data.demo import build_affiliates, build_licenses, _rng, _month_labels
from app.data.resources import build_resources
from app.models import (
    AiConsumption,
    AiConsumptionRow,
    AiSourceSummary,
    AiTrendPoint,
)

# Approx blended $ per 1K tokens (demo).
_PER_1K = 0.004


def build_ai_consumption(affiliate_id: str | None) -> AiConsumption:
    affiliates = build_affiliates()
    if affiliate_id:
        affiliates = [a for a in affiliates if a.affiliate_id == affiliate_id]

    rows: list[AiConsumptionRow] = []

    for aff in affiliates:
        r = _rng(f"ai:{aff.affiliate_id}")
        resources = build_resources(aff.affiliate_id)

        # Azure OpenAI + Foundry: cost is in FOCUS; tokens from Azure Monitor metrics.
        for rc in resources:
            if rc.service_name in ("Azure OpenAI", "Azure AI Foundry"):
                tokens = rc.cost / _PER_1K * 1000
                rows.append(
                    AiConsumptionRow(
                        affiliate_id=aff.affiliate_id,
                        source=rc.service_name,
                        origin="FOCUS cost + Azure Monitor tokens",
                        metric_type="tokens",
                        quantity=round(tokens, 0),
                        cost=rc.cost,
                    )
                )
            elif rc.service_name == "Defender for Cloud":
                pass

        # Security Copilot (SCU) + Fabric Copilot (CU) — provisioned in Azure.
        rows.append(
            AiConsumptionRow(
                affiliate_id=aff.affiliate_id,
                source="Security Copilot",
                origin="Azure (SCU meters in FOCUS)",
                metric_type="SCU",
                quantity=r.randint(1, 6),
                cost=round(r.uniform(500, 4000), 2),
            )
        )

        # GitHub Copilot: seats + usage from GitHub APIs (not Azure billing by default).
        gh_seats = r.randint(50, 900)
        rows.append(
            AiConsumptionRow(
                affiliate_id=aff.affiliate_id,
                source="GitHub Copilot",
                origin="GitHub billing + metrics API",
                metric_type="seats",
                quantity=gh_seats,
                cost=round(gh_seats * 19.0, 2),  # ~$19/seat/mo enterprise
            )
        )

        # M365 Copilot: seats from license feed; usage via Graph usage reports.
        m365 = [l for l in build_licenses(aff.affiliate_id) if l.sku.startswith("M365")]
        m365_seats = int(sum(l.assigned for l in m365) * r.uniform(0.1, 0.3)) if m365 else r.randint(20, 400)
        rows.append(
            AiConsumptionRow(
                affiliate_id=aff.affiliate_id,
                source="M365 Copilot",
                origin="M365 commerce + Graph usage",
                metric_type="seats",
                quantity=m365_seats,
                cost=round(m365_seats * 30.0, 2),  # $30/seat/mo
            )
        )

    # Aggregate by source.
    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        a = agg.setdefault(row.source, {"cost": 0.0, "qty": 0.0, "metric": row.metric_type})
        a["cost"] += row.cost
        a["qty"] += row.quantity
    by_source = sorted(
        (
            AiSourceSummary(source=s, cost=round(v["cost"], 2), quantity=round(v["qty"], 0), metric_type=str(v["metric"]))
            for s, v in agg.items()
        ),
        key=lambda x: x.cost,
        reverse=True,
    )

    total_ai_cost = round(sum(r.cost for r in rows), 2)
    total_tokens = round(sum(r.quantity for r in rows if r.metric_type == "tokens"), 0)
    copilot_seats = int(sum(r.quantity for r in rows if r.metric_type == "seats"))

    # Token trend over 12 months.
    rr = _rng(f"aitrend:{affiliate_id or 'ALL'}")
    months = _month_labels(12)
    trend: list[AiTrendPoint] = []
    for idx, m in enumerate(months):
        growth = 1 + 0.35 * (idx / len(months)) + rr.uniform(-0.05, 0.05)
        tks = total_tokens / len(months) * growth
        trend.append(AiTrendPoint(month=m, tokens=round(tks, 0), cost=round(tks / 1000 * _PER_1K, 2)))

    return AiConsumption(
        total_ai_cost=total_ai_cost,
        total_tokens=total_tokens,
        copilot_seats=copilot_seats,
        avg_acceptance_pct=round(rr.uniform(28, 42), 1),
        by_source=by_source,
        trend=trend,
        rows=sorted(rows, key=lambda x: x.cost, reverse=True)[:40],
    )
