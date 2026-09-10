"""Live provider mapping tests — use a fake Cost Management client (no Azure)."""
from __future__ import annotations

from app.config import Settings
from app.services.azure_provider import AzureDataProvider


class _FakeClient:
    """Stand-in for AzureCostClient returning canned rows."""

    def __init__(self, settings: Settings) -> None:  # noqa: D401
        self.settings = settings

    def list_subscriptions(self):
        return [
            {"subscription_id": "sub-1", "display_name": "Prod", "state": "Enabled", "tenant_id": "t1"},
            {"subscription_id": "sub-2", "display_name": "Dev", "state": "Disabled", "tenant_id": "t1"},
        ]

    def monthly_totals(self, sid, months, amortized=False, tenant_id=None):
        base = 100.0 if amortized else 120.0
        return [
            {"month": "2026-07", "cost": base, "cost_usd": base, "currency": "USD"},
            {"month": "2026-08", "cost": base + 30, "cost_usd": base + 30, "currency": "USD"},
        ]

    def resource_costs(self, sid, months, tenant_id=None):
        return [
            {
                "resource_id": f"/subscriptions/{sid}/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm01",
                "service_name": "Virtual Machines",
                "cost": 80.0,
                "cost_usd": 80.0,
                "currency": "USD",
            },
            {
                "resource_id": f"/subscriptions/{sid}/resourceGroups/rg-ai/providers/Microsoft.CognitiveServices/accounts/oai01",
                "service_name": "Azure OpenAI",
                "cost": 40.0,
                "cost_usd": 40.0,
                "currency": "USD",
            },
        ]

    def dimension_totals(self, sid, dimension, months, tenant_id=None):
        return [
            {"key": "OnDemand", "cost": 90.0, "currency": "USD"},
            {"key": "Reservation", "cost": 30.0, "currency": "USD"},
        ]

    def reservation_recommendations(self, sid, tenant_id=None):
        return [
            {
                "resource_type": "VirtualMachines",
                "sku": "Standard_D2s_v3",
                "term": "1 year",
                "scope": "Shared",
                "recommended_quantity": 3,
                "monthly_savings": 120.0,
                "savings_pct": 30.0,
                "monthly_cost": 400.0,
                "currency": "USD",
            }
        ]

    def savings_plan_recommendations(self, sid, tenant_id=None):
        return {"commitment": 500.0, "savings": 60.0, "currency": "USD"}

    def realized_commitment_value(self, sid, months, tenant_id=None):
        return 25.0

    def commitment_inventory(self, tenant_id=None):
        return {"reservations": 1, "savings_plans": 2, "commitment": 1000.0}

    def macc_lots(self, billing_account, tenant_id=None):
        return []

    def macc_events(self, billing_account, start_date, end_date, tenant_id=None):
        return []

    def monitor_token_totals(self, resource_id, months, tenant_id=None):
        return {}


class _FakeGraph:
    def __init__(self, skus=None) -> None:
        self._skus = skus if skus is not None else []

    def subscribed_skus(self, tenant_id=None):
        return list(self._skus)


class _FakeGitHub:
    def __init__(self, summaries=None) -> None:
        self._summaries = summaries or {}

    def copilot_summary(self, org):
        return self._summaries.get(org, {"org": org, "seats": 0, "cost": 0.0, "acceptance_pct": 0.0})


def _provider(skus=None, github=None) -> AzureDataProvider:
    p = AzureDataProvider(Settings(use_mock=False))
    p.client = _FakeClient(p.settings)  # type: ignore[assignment]
    p.graph = _FakeGraph(skus)  # type: ignore[assignment]
    p.github = _FakeGitHub(github)  # type: ignore[assignment]
    return p


def test_affiliates_from_subscriptions() -> None:
    affs = _provider().affiliates()
    assert [a.affiliate_id for a in affs] == ["sub-1", "sub-2"]
    assert affs[0].status.value == "Active"
    assert affs[1].status.value == "Paused"


def test_cost_summary_aggregates_usd() -> None:
    cost = _provider().cost_summary(None)
    # two subs, two months; last month = (150)*2 = 300
    assert cost.total_cost_mtd == 300.0
    assert cost.total_cost_last_month == 240.0
    assert cost.mom_change_pct == 25.0
    services = {s.service for s in cost.by_service}
    assert "Virtual Machines" in services and "Azure OpenAI" in services


def test_breakdown_four_levels() -> None:
    detail = _provider().affiliate_breakdown("sub-1")
    assert detail is not None
    assert detail.resource_count == 2
    cat = detail.breakdown[0]
    assert cat.level == 1
    assert cat.children[0].level == 2
    assert cat.children[0].children[0].level == 3
    assert cat.children[0].children[0].children[0].level == 4


def test_breakdown_unknown_affiliate() -> None:
    assert _provider().affiliate_breakdown("nope") is None


def test_hierarchy_subscription_root() -> None:
    h = _provider().hierarchy("sub-1")
    assert h is not None
    assert h.root.node_type == "affiliate"
    assert {c.node_type for c in h.root.children} == {"resourceGroup"}


def test_macc_empty_on_plain_subscription() -> None:
    p = _provider()
    assert p.macc_balances() == []
    assert p.macc_detail("sub-1") is None


def test_ai_consumption_from_ai_meters() -> None:
    ai = _provider().ai_consumption(None)
    # Azure OpenAI on both subs: 40 * 2 = 80
    assert ai.total_ai_cost == 80.0
    assert any(s.source == "Azure OpenAI" for s in ai.by_source)
    assert len(ai.trend) == len(_provider().cost_summary(None).trend)


def test_offer_mix_from_pricing_model() -> None:
    mix = _provider().offer_mix()
    names = {m.name for m in mix}
    assert "OnDemand" in names and "Reservation" in names


def test_service_category_ai() -> None:
    from app.services.service_catalog import is_ai_service, service_category

    assert service_category("Foundry Models") == "AI + ML"
    assert service_category("MS Bing Services") == "AI + ML"
    assert service_category("Azure OpenAI") == "AI + ML"
    assert is_ai_service("Azure AI Foundry")
    assert service_category("Virtual Machines") == "Compute"


def test_rate_optimization_from_recommendations() -> None:
    ro = _provider().rate_optimization(None)
    # VM recommendation on both subs: 120 * 2 = 240 monthly savings
    assert ro.potential_reservation_savings == 240.0
    assert ro.savings_plan_commitment == 1000.0  # 500 * 2 subs
    assert ro.recommendations[0].service == "Virtual Machines"
    assert ro.recommendations[0].term == "1 year"
    assert any(s.service == "Virtual Machines" for s in ro.by_service)
    # existing commitments: one tenant (t1) -> 1 reservation + 2 savings plans
    assert ro.active_savings_plans == 3
    assert ro.savings_to_date == 50.0  # realized 25 * 2 subs


def test_licenses_from_graph() -> None:
    skus = [
        {"product": "Microsoft 365 E5", "sku": "SPE_E5", "assigned": 100, "consumed": 90, "unit_cost": 57.0},
        {"product": "Power BI Pro", "sku": "POWER_BI_PRO", "assigned": 40, "consumed": 30, "unit_cost": 10.0},
    ]
    p = _provider(skus=skus)
    lic = p.licenses(None)
    # two subs share tenant t1 -> Graph read once per tenant, applied to each affiliate
    assert len(lic) == 4
    e5 = next(l for l in lic if l.sku == "SPE_E5")
    assert e5.assigned == 100 and e5.consumed == 90 and e5.unit_cost == 57.0
    # TCO now includes real license spend
    tco = p.tco(None)
    assert tco.license_cost > 0
    assert tco.total == round(tco.azure_cost + tco.license_cost, 2)


def test_macc_from_lots_and_events() -> None:
    from app.services.affiliate_registry import AffiliateDef, AffiliateRegistry

    p = _provider()
    p._registry = AffiliateRegistry(
        affiliates=[
            AffiliateDef(
                affiliate_id="acme",
                name="Acme Corp",
                subscription_ids=["sub-a"],
                tenant_id="t1",
                agreement_type="MCA",
                billing_account="BA-1",
            )
        ]
    )
    p.client.macc_lots = lambda ba, tenant_id=None: [  # type: ignore[assignment]
        {
            "properties": {
                "originalAmount": {"value": 1_000_000.0, "currency": "USD"},
                "closedBalance": {"value": 600_000.0, "currency": "USD"},
                "startDate": "2025-01-01T00:00:00Z",
                "expirationDate": "2027-12-31T00:00:00Z",
            }
        }
    ]
    p.client.macc_events = lambda ba, s, e, tenant_id=None: [  # type: ignore[assignment]
        {"properties": {"transactionDate": "2026-07-15T00:00:00Z", "charges": {"value": 40000.0}}},
        {"properties": {"transactionDate": "2026-08-15T00:00:00Z", "charges": {"value": 50000.0}}},
    ]
    balances = p.macc_balances()
    assert len(balances) == 1
    b = balances[0]
    assert b.commitment_amount == 1_000_000.0
    assert b.remaining_balance == 600_000.0
    assert b.consumed_amount == 400_000.0
    detail = p.macc_detail("acme")
    assert detail is not None
    assert len(detail.trend) == 2
    assert detail.events[0].charges in (40000.0, 50000.0)
    # prepayment aggregates real MACC balances
    pre = p.prepayment()
    assert pre.macc_total_balance == 1_000_000.0
    assert pre.macc_utilized == 400_000.0


def test_tco_azure_only() -> None:
    tco = _provider().tco(None)
    assert tco.azure_cost == tco.total
    assert tco.license_cost == 0.0


def test_ai_copilot_seats_and_tokens() -> None:
    from app.services.affiliate_registry import AffiliateDef, AffiliateRegistry

    skus = [{"product": "Microsoft 365 Copilot", "sku": "Microsoft_365_Copilot", "assigned": 200, "consumed": 180, "unit_cost": 30.0}]
    github = {"acme-org": {"org": "acme-org", "seats": 150, "cost": 5850.0, "acceptance_pct": 34.0}}
    p = _provider(skus=skus, github=github)
    p._registry = AffiliateRegistry(
        affiliates=[
            AffiliateDef(
                affiliate_id="acme",
                name="Acme Corp",
                subscription_ids=["sub-a"],
                tenant_id="t1",
                github_orgs=["acme-org"],
            )
        ]
    )
    p.client.monitor_token_totals = lambda rid, months, tenant_id=None: {"2026-07": 1_000_000.0, "2026-08": 500_000.0}  # type: ignore[assignment]
    ai = p.ai_consumption(None)
    assert ai.copilot_seats == 350  # 150 GitHub + 200 M365
    assert ai.avg_acceptance_pct == 34.0
    assert ai.total_tokens == 1_500_000.0
    sources = {s.source for s in ai.by_source}
    assert {"GitHub Copilot", "M365 Copilot", "Azure OpenAI"} <= sources
    # TCO: external Copilot = GitHub only (M365 Copilot already in license_cost)
    tco = p.tco(None)
    assert tco.external_copilot_cost == 5850.0
    assert tco.license_cost == round(200 * 30.0, 2)  # M365 Copilot seats as an Entra license
    assert tco.total == round(tco.azure_cost + tco.license_cost + tco.external_copilot_cost, 2)


def test_registry_mode_multi_subscription() -> None:
    from app.services.affiliate_registry import AffiliateDef, AffiliateRegistry

    p = _provider()
    p._registry = AffiliateRegistry(
        affiliates=[
            AffiliateDef(
                affiliate_id="acme",
                name="Acme Corp",
                subscription_ids=["sub-a", "sub-b"],
                tenant_id="tenant-x",
                agreement_type="EA",
                billing_account="BA-1",
            )
        ]
    )
    affs = p.affiliates()
    assert [a.affiliate_id for a in affs] == ["acme"]
    assert affs[0].agreement_type.value == "EA"
    assert affs[0].tenant_id == "tenant-x"
    # two subscriptions aggregate: last-month total = 150 * 2 = 300
    assert p.cost_summary("acme").total_cost_mtd == 300.0
    # breakdown/hierarchy resolve the affiliate id (not a raw subscription id)
    assert p.affiliate_breakdown("acme") is not None
    assert p.hierarchy("acme").root.node_type == "affiliate"
    assert p.affiliate_breakdown("sub-a") is None
