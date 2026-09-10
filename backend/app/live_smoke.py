"""Smoke test for live Azure Cost Management pulls.

Run against a real subscription (after ``az login``) to verify the live provider
works end-to-end and to preview the numbers the dashboard will show:

    cd backend
    python -m app.live_smoke                # all accessible subscriptions
    python -m app.live_smoke <subscription> # one subscription

It forces ``USE_MOCK=false`` for the process regardless of your .env.
"""
from __future__ import annotations

import logging
import os
import sys

os.environ["USE_MOCK"] = "false"

from app.config import get_settings  # noqa: E402
from app.services.azure_provider import AzureDataProvider  # noqa: E402


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if len(argv) > 1:
        os.environ["AZURE_SUBSCRIPTION_IDS"] = argv[1]
        get_settings.cache_clear()
        settings = get_settings()

    provider = AzureDataProvider(settings)

    print("== Subscriptions (affiliates) ==")
    affiliates = provider.affiliates()
    for a in affiliates:
        print(f"  {a.affiliate_id}  {a.name}  ({a.status.value}, tenant {a.tenant_id or '-'})")
    if not affiliates:
        print("  (none — check permissions / az login)")
        return 1

    print(f"\n== Portfolio summary (history: {settings.history_months} months) ==")
    summary = provider.portfolio_summary()
    print(f"  subscriptions: {summary.affiliate_count}  active: {summary.active_count}")
    print(f"  latest-month Azure cost (USD): {summary.total_cost_mtd:,.2f}")

    print("\n== Cost trend (all subscriptions) ==")
    cost = provider.cost_summary(None)
    for p in cost.trend:
        print(f"  {p.month}  actual={p.cost:>12,.2f}  amortized={p.amortized_cost:>12,.2f}")
    print(f"  MoM change: {cost.mom_change_pct:+.1f}%")

    print("\n== Top services ==")
    for s in cost.by_service[:10]:
        print(f"  {s.service:<40} {s.cost:>12,.2f}")

    first = affiliates[0].affiliate_id
    print(f"\n== Top resources for {first} ==")
    resources = provider.affiliate_resources(first)
    for r in resources[:10]:
        print(f"  {r.cost:>12,.2f}  {r.service_name:<28} {r.resource_name} ({r.resource_group})")
    print(f"  total resources: {len(resources)}")

    print("\n== Rate optimization (reservations + savings plans) ==")
    ro = provider.rate_optimization(None)
    print(f"  potential RI savings/mo: {ro.potential_reservation_savings:,.2f}")
    print(f"  savings-plan commitment: {ro.savings_plan_commitment:,.2f}")
    print(f"  active commitments: {ro.active_savings_plans}   realized value: {ro.savings_to_date:,.2f}")
    print(f"  recommendations: {len(ro.recommendations)}")
    for rec in ro.recommendations[:5]:
        print(f"    {rec.monthly_savings:>10,.2f}/mo  {rec.service} {rec.sku} ({rec.term}, qty {rec.recommended_quantity})")

    print("\n== Licenses (Microsoft Graph subscribedSkus) ==")
    lic = provider.licenses(None)
    for l in lic[:10]:
        print(f"  {l.assigned:>6} / {l.consumed:<6}  {l.product} ({l.sku})  ${l.unit_cost}/seat")
    if not lic:
        print("  (none — grant Graph Organization.Read.All to read license seats)")

    print("\n== MACC ==")
    balances = provider.macc_balances()
    for b in balances:
        print(f"  {b.affiliate_name}: {b.consumed_amount:,.0f}/{b.commitment_amount:,.0f} {b.currency} consumed")
    if not balances:
        print("  (none — set billing_account + grant Billing Reader for MACC affiliates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
