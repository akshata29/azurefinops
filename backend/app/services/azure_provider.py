"""Real Azure data provider — maps Cost Management output onto the API models.

Used when ``USE_MOCK=false``. It turns each accessible **subscription** (or
registry-defined **affiliate**) into an affiliate and fills every dashboard model
from live data:

* cost / breakdown / hierarchy / AI / TCO  -> Azure Cost Management
* reservation + savings-plan recommendations, existing commitments -> Consumption
  / Cost Management / BillingBenefits
* licenses -> Microsoft Graph ``subscribedSkus`` (+ price map)
* MACC commitments -> Consumption ``lots`` + ``events`` (per billing account)

Signals with no source on a given affiliate (e.g. no MACC, no Graph consent)
degrade to honest zeros/empties instead of raising, so the dashboard keeps
working against real spend.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.models import (
    Affiliate,
    AffiliateCostDetail,
    AffiliateHierarchy,
    AgreementType,
    AiConsumption,
    AiConsumptionRow,
    AiSourceSummary,
    AiTrendPoint,
    BreakdownNode,
    CostByService,
    CostPoint,
    CostSummary,
    DeploymentTpm,
    HierarchyNode,
    License,
    MaccBalance,
    MaccDetail,
    MaccEvent,
    MaccStatus,
    MaccTrendPoint,
    OfferMixSlice,
    OnboardingStatus,
    PortfolioSummary,
    PrepaymentSummary,
    RateOptimization,
    ReservationRecommendation,
    ResourceCost,
    SavingsByService,
    TcoSourceSlice,
    TcoSummary,
    TcoTrendPoint,
)
from app.services.azure_cost import AzureCostClient
from app.services.service_catalog import is_ai_service, service_category

logger = logging.getLogger(__name__)

# Azure reservation ``resourceType`` -> readable service name.
_RESERVATION_SERVICE = {
    "VirtualMachines": "Virtual Machines",
    "SqlDatabases": "Azure SQL Database",
    "SqlDataWarehouse": "Azure Synapse (SQL DW)",
    "SuseLinux": "SUSE Linux",
    "RedHat": "Red Hat",
    "RedHatOsa": "Red Hat OSA",
    "CosmosDb": "Cosmos DB",
    "MySql": "Azure Database for MySQL",
    "MariaDb": "Azure Database for MariaDB",
    "PostgreSql": "Azure Database for PostgreSQL",
    "Databricks": "Azure Databricks",
    "AppService": "App Service",
    "BlockBlob": "Blob Storage",
    "ManagedDisk": "Managed Disks",
    "AzureDataExplorer": "Azure Data Explorer",
    "NetAppFiles": "Azure NetApp Files",
    "AzureFiles": "Azure Files",
    "DedicatedHost": "Dedicated Host",
    "VMwareCloudSimple": "Azure VMware Solution",
}


def _spaced(camel: str) -> str:
    """Turn a CamelCase resourceType into spaced words as a fallback label."""
    import re

    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", camel) or camel


def _parse_resource_id(resource_id: str) -> dict[str, str]:
    """Extract resource group / type / name from an ARM resource id."""
    parts = [p for p in resource_id.split("/") if p]
    info = {"resource_group": "(unassigned)", "resource_type": "Other", "resource_name": resource_id or "(account)"}
    lowered = [p.lower() for p in parts]
    if "resourcegroups" in lowered:
        idx = lowered.index("resourcegroups")
        if idx + 1 < len(parts):
            info["resource_group"] = parts[idx + 1]
    if "providers" in lowered:
        idx = lowered.index("providers")
        # providers/<namespace>/<type>/<name>[/<subtype>/<subname>]
        tail = parts[idx + 1 :]
        if len(tail) >= 2:
            info["resource_type"] = f"{tail[0]}/{tail[1]}"
        if len(tail) >= 3:
            info["resource_name"] = tail[-1]
    elif parts:
        info["resource_name"] = parts[-1]
    return info


class AzureDataProvider:
    """Live provider backed by Azure Cost Management.

    Affiliates come from an :mod:`affiliate_registry` file when present (each
    affiliate may span multiple subscriptions, optionally in its own tenant);
    otherwise every subscription the signed-in identity can read becomes its own
    affiliate (zero-config single-tenant path).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AzureCostClient(settings)
        self._months = max(1, settings.history_months)
        from app.services.affiliate_registry import load_registry  # lazy
        from app.services.graph_client import GraphClient  # lazy

        self._registry = load_registry(settings)
        self.graph = GraphClient(self.client.token_provider, self.client.cache)
        from app.services.github_client import GitHubClient  # lazy

        self.github = GitHubClient(settings.github_token, self.client.cache, settings.github_copilot_seat_cost)

    # -- affiliate resolution ---------------------------------------------- #
    def _affiliate_defs(self) -> list[dict]:
        """Normalised affiliate records: id, name, tenant, subs, agreement, etc."""
        if not self._registry.is_empty():
            defs = []
            for a in self._registry.affiliates:
                status = OnboardingStatus.ACTIVE
                defs.append(
                    {
                        "affiliate_id": a.affiliate_id,
                        "name": a.name,
                        "tenant_id": a.tenant_id,
                        "agreement_type": a.agreement_type,
                        "billing_account": a.billing_account or (a.subscription_ids[0] if a.subscription_ids else ""),
                        "billing_profile": a.billing_profile,
                        "subscription_ids": a.subscription_ids,
                        "status": status,
                        "github_orgs": a.github_orgs or self.settings.github_org_list,
                    }
                )
            return defs
        # Discovery mode — one affiliate per subscription (no billing account => no MACC).
        defs = []
        for s in self.client.list_subscriptions():
            state = (s.get("state") or "Enabled").lower()
            defs.append(
                {
                    "affiliate_id": s["subscription_id"],
                    "name": s.get("display_name") or s["subscription_id"],
                    "tenant_id": s.get("tenant_id") or "",
                    "agreement_type": "MCA",
                    "billing_account": "",
                    "billing_profile": None,
                    "subscription_ids": [s["subscription_id"]],
                    "status": OnboardingStatus.ACTIVE if state == "enabled" else OnboardingStatus.PAUSED,
                    "github_orgs": self.settings.github_org_list,
                }
            )
        return defs

    def _affiliate_def(self, affiliate_id: str) -> dict | None:
        return next((d for d in self._affiliate_defs() if d["affiliate_id"] == affiliate_id), None)

    def _targets(self, affiliate_id: str | None) -> list[tuple[str, str]]:
        """(subscription_id, tenant_id) pairs for one affiliate, or all of them."""
        defs = self._affiliate_defs()
        if affiliate_id is not None:
            defs = [d for d in defs if d["affiliate_id"] == affiliate_id]
        pairs: list[tuple[str, str]] = []
        for d in defs:
            for sid in d["subscription_ids"]:
                pairs.append((sid, d["tenant_id"]))
        return pairs

    def _to_affiliate(self, d: dict) -> Affiliate:
        agreement = AgreementType.EA if str(d.get("agreement_type")).upper() == "EA" else AgreementType.MCA
        subs = d.get("subscription_ids") or []
        billing_account = d.get("billing_account") or (subs[0] if subs else "")
        return Affiliate(
            affiliate_id=d["affiliate_id"],
            name=d["name"],
            tenant_id=d.get("tenant_id") or "",
            agreement_type=agreement,
            billing_account=billing_account,
            billing_profile=d.get("billing_profile"),
            status=d.get("status", OnboardingStatus.ACTIVE),
            onboarded_on=date.today(),
            last_data_refresh=date.today(),
        )

    def affiliates(self) -> list[Affiliate]:
        return [self._to_affiliate(d) for d in self._affiliate_defs()]

    def _affiliate_name(self, affiliate_id: str) -> str:
        d = self._affiliate_def(affiliate_id)
        return d["name"] if d else affiliate_id

    def _affiliate_tenant(self, affiliate_id: str) -> str | None:
        d = self._affiliate_def(affiliate_id)
        return (d.get("tenant_id") or None) if d else None

    # -- MACC (Microsoft Azure Consumption Commitment) --------------------- #
    def _macc_balance_for(self, d: dict) -> MaccBalance | None:
        billing_account = d.get("billing_account")
        if not billing_account:
            return None
        tenant = d.get("tenant_id") or None
        lots = self.client.macc_lots(billing_account, tenant_id=tenant)
        if not lots:
            return None
        commitment = remaining = 0.0
        currency = "USD"
        start: date | None = None
        end: date | None = None
        for lot in lots:
            p = lot.get("properties", {})
            orig = p.get("originalAmount") or {}
            closed = p.get("closedBalance") or {}
            commitment += _num(orig.get("value"))
            remaining += _num(closed.get("value"))
            currency = orig.get("currency") or currency
            start = _min_date(start, _parse_date(p.get("startDate")))
            end = _max_date(end, _parse_date(p.get("expirationDate")))
        consumed = round(commitment - remaining, 2)
        today = date.today()
        start = start or today
        end = end or today
        days_remaining = max(0, (end - today).days)
        pct = round(consumed / commitment * 100, 1) if commitment else 0.0
        elapsed = max(1, (today - start).days)
        term_days = max(1, (end - start).days)
        linear_expected = elapsed / term_days * 100
        on_track = abs(pct - linear_expected) <= 12
        monthly_burn = consumed / max(1.0, elapsed / 30.0)
        projected = today + timedelta(days=int((remaining / monthly_burn) * 30)) if monthly_burn > 0 else None
        return MaccBalance(
            affiliate_id=d["affiliate_id"],
            affiliate_name=d["name"],
            commitment_amount=round(commitment, 2),
            remaining_balance=round(remaining, 2),
            consumed_amount=consumed,
            percent_consumed=pct,
            currency=currency,
            start_date=start,
            end_date=end,
            days_remaining=days_remaining,
            status=MaccStatus.ACTIVE if days_remaining > 0 else MaccStatus.EXPIRED,
            projected_exhaustion_date=projected if projected and projected <= end else None,
            on_track=on_track,
        )

    def macc_balances(self) -> list[MaccBalance]:
        out: list[MaccBalance] = []
        for d in self._affiliate_defs():
            try:
                bal = self._macc_balance_for(d)
            except Exception as exc:  # pragma: no cover - permission/no-MACC
                logger.warning("macc_balances: affiliate %s failed: %s", d["affiliate_id"], exc)
                bal = None
            if bal is not None:
                out.append(bal)
        return out

    def macc_detail(self, affiliate_id: str) -> MaccDetail | None:
        d = self._affiliate_def(affiliate_id)
        if d is None:
            return None
        balance = self._macc_balance_for(d)
        if balance is None:
            return None
        billing_account = d["billing_account"]
        tenant = d.get("tenant_id") or None
        start = balance.start_date.isoformat()
        end = date.today().isoformat()
        raw_events = self.client.macc_events(billing_account, start, end, tenant_id=tenant)
        monthly: dict[str, float] = {}
        for ev in raw_events:
            p = ev.get("properties", {})
            month = str(p.get("transactionDate") or "")[:7]
            if not month:
                continue
            charge = _num((p.get("charges") or {}).get("value")) or _num(p.get("charges"))
            monthly[month] = monthly.get(month, 0.0) + charge
        trend: list[MaccTrendPoint] = []
        events: list[MaccEvent] = []
        cumulative = 0.0
        for month in sorted(monthly):
            charge = monthly[month]
            cumulative += charge
            remaining = round(balance.commitment_amount - cumulative, 2)
            trend.append(MaccTrendPoint(month=month, remaining_balance=remaining, consumed_cumulative=round(cumulative, 2)))
            events.append(
                MaccEvent(
                    affiliate_id=affiliate_id,
                    event_date=date(int(month[:4]), int(month[5:7]), 1),
                    description=f"MACC drawdown — {month}",
                    charges=round(charge, 2),
                    remaining_after=remaining,
                    currency=balance.currency,
                )
            )
        return MaccDetail(balance=balance, trend=trend, events=list(reversed(events)))

    # -- cost -------------------------------------------------------------- #
    def _month_window(self) -> list[str]:
        today = datetime.now(timezone.utc).date().replace(day=1)
        labels: list[str] = []
        y, m = today.year, today.month
        for _ in range(self._months):
            labels.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        return list(reversed(labels))

    def cost_summary(self, affiliate_id: str | None) -> CostSummary:
        targets = self._targets(affiliate_id)
        actual: dict[str, float] = {}
        amortized: dict[str, float] = {}
        service_totals: dict[str, float] = {}
        for sid, tenant in targets:
            try:
                for row in self.client.monthly_totals(sid, self._months, amortized=False, tenant_id=tenant):
                    actual[row["month"]] = actual.get(row["month"], 0.0) + row["cost_usd"]
                for row in self.client.monthly_totals(sid, self._months, amortized=True, tenant_id=tenant):
                    amortized[row["month"]] = amortized.get(row["month"], 0.0) + row["cost_usd"]
                for row in self.client.resource_costs(sid, self._months, tenant_id=tenant):
                    service_totals[row["service_name"]] = service_totals.get(row["service_name"], 0.0) + row["cost_usd"]
            except Exception as exc:  # pragma: no cover - permission/transient
                logger.warning("cost_summary: subscription %s failed: %s", sid, exc)

        months = sorted(set(actual) | set(amortized)) or self._month_window()
        trend = [
            CostPoint(
                month=m,
                affiliate_id=affiliate_id or "ALL",
                cost=round(actual.get(m, 0.0), 2),
                amortized_cost=round(amortized.get(m, actual.get(m, 0.0)), 2),
            )
            for m in months
        ]
        mtd = trend[-1].cost if trend else 0.0
        last = trend[-2].cost if len(trend) > 1 else 0.0
        mom = round((mtd - last) / last * 100, 1) if last else 0.0
        by_service = sorted(
            (CostByService(service=s, cost=round(v, 2)) for s, v in service_totals.items() if v),
            key=lambda x: x.cost,
            reverse=True,
        )
        return CostSummary(
            total_cost_mtd=round(mtd, 2),
            total_cost_last_month=round(last, 2),
            mom_change_pct=mom,
            trend=trend,
            by_service=by_service,
        )

    def licenses(self, affiliate_id: str | None) -> list[License]:
        defs = self._affiliate_defs()
        if affiliate_id is not None:
            defs = [d for d in defs if d["affiliate_id"] == affiliate_id]
        # Read each distinct tenant once; a tenant's SKUs apply to its affiliates.
        out: list[License] = []
        seen_tenants: dict[str, list[dict]] = {}
        for d in defs:
            tenant = d.get("tenant_id") or ""
            if tenant not in seen_tenants:
                try:
                    seen_tenants[tenant] = self.graph.subscribed_skus(tenant or None)
                except Exception as exc:  # pragma: no cover - consent/permission
                    logger.warning("licenses: tenant %s failed: %s", tenant or "default", exc)
                    seen_tenants[tenant] = []
            for sku in seen_tenants[tenant]:
                out.append(
                    License(
                        affiliate_id=d["affiliate_id"],
                        product=sku["product"],
                        sku=sku["sku"],
                        assigned=sku["assigned"],
                        consumed=sku["consumed"],
                        unit_cost=sku["unit_cost"],
                        renewal_date=None,
                    )
                )
        return out

    def portfolio_summary(self) -> PortfolioSummary:
        affiliates = self.affiliates()
        cost_mtd = self.cost_summary(None).total_cost_mtd
        return PortfolioSummary(
            affiliate_count=len(affiliates),
            active_count=sum(1 for a in affiliates if a.status == OnboardingStatus.ACTIVE),
            total_commitment=0.0,
            total_remaining=0.0,
            total_consumed=0.0,
            percent_consumed=0.0,
            total_cost_mtd=round(cost_mtd, 2),
            at_risk_count=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # -- resource-level ---------------------------------------------------- #
    def affiliate_resources(self, affiliate_id: str) -> list[ResourceCost]:
        rows: list[ResourceCost] = []
        for sid, tenant in self._targets(affiliate_id):
            try:
                raw = self.client.resource_costs(sid, self._months, tenant_id=tenant)
            except Exception as exc:  # pragma: no cover - permission/transient
                logger.warning("affiliate_resources: subscription %s failed: %s", sid, exc)
                continue
            for row in raw:
                info = _parse_resource_id(row["resource_id"])
                rows.append(
                    ResourceCost(
                        affiliate_id=affiliate_id,
                        resource_name=info["resource_name"],
                        resource_group=info["resource_group"],
                        service_category=service_category(row["service_name"]),
                        service_name=row["service_name"],
                        resource_type=info["resource_type"],
                        region="",
                        cost=round(row["cost_usd"], 2),
                    )
                )
        rows.sort(key=lambda r: r.cost, reverse=True)
        return rows

    def affiliate_breakdown(self, affiliate_id: str) -> AffiliateCostDetail | None:
        if self._affiliate_def(affiliate_id) is None:
            return None
        resources = self.affiliate_resources(affiliate_id)
        total = sum(r.cost for r in resources)

        cat_nodes: dict[str, BreakdownNode] = {}
        for rc in resources:
            cat = cat_nodes.setdefault(rc.service_category, BreakdownNode(name=rc.service_category, level=1, cost=0.0))
            cat.cost += rc.cost
            svc = next((c for c in cat.children if c.name == rc.service_name), None)
            if svc is None:
                svc = BreakdownNode(name=rc.service_name, level=2, cost=0.0)
                cat.children.append(svc)
            svc.cost += rc.cost
            rt = next((c for c in svc.children if c.name == rc.resource_type), None)
            if rt is None:
                rt = BreakdownNode(name=rc.resource_type, level=3, cost=0.0)
                svc.children.append(rt)
            rt.cost += rc.cost
            rt.children.append(
                BreakdownNode(name=f"{rc.resource_name} ({rc.resource_group})", level=4, cost=rc.cost)
            )

        def finalize(nodes: list[BreakdownNode], parent_cost: float) -> list[BreakdownNode]:
            nodes.sort(key=lambda n: n.cost, reverse=True)
            for n in nodes:
                n.cost = round(n.cost, 2)
                n.pct_of_parent = round(n.cost / parent_cost * 100, 1) if parent_cost else 0.0
                if n.children:
                    n.children = finalize(n.children, n.cost)
            return nodes

        breakdown = finalize(list(cat_nodes.values()), total)
        return AffiliateCostDetail(
            affiliate_id=affiliate_id,
            affiliate_name=self._affiliate_name(affiliate_id),
            total_cost=round(total, 2),
            resource_count=len(resources),
            breakdown=breakdown,
            top_resources=resources[:10],
        )

    def hierarchy(self, affiliate_id: str) -> AffiliateHierarchy | None:
        if self._affiliate_def(affiliate_id) is None:
            return None
        resources = self.affiliate_resources(affiliate_id)
        total = sum(r.cost for r in resources)
        name = self._affiliate_name(affiliate_id)
        root = HierarchyNode(name=name, node_type="affiliate", identifier=affiliate_id, cost=total)

        for rc in resources:
            rg = next((c for c in root.children if c.name == rc.resource_group), None)
            if rg is None:
                rg = HierarchyNode(name=rc.resource_group, node_type="resourceGroup", cost=0.0)
                root.children.append(rg)
            rg.cost += rc.cost
            rg.children.append(
                HierarchyNode(name=rc.resource_name, node_type="resource", identifier=rc.service_name, cost=rc.cost)
            )

        def finalize(nodes: list[HierarchyNode], parent_cost: float) -> list[HierarchyNode]:
            nodes.sort(key=lambda n: n.cost, reverse=True)
            for n in nodes:
                n.cost = round(n.cost, 2)
                n.pct_of_parent = round(n.cost / parent_cost * 100, 1) if parent_cost else 0.0
                if n.children:
                    n.children = finalize(n.children, n.cost)
            return nodes

        root.children = finalize(root.children, total)
        root.cost = round(total, 2)
        return AffiliateHierarchy(affiliate_id=affiliate_id, affiliate_name=name, total_cost=round(total, 2), root=root)

    # -- analytics slices -------------------------------------------------- #
    def rate_optimization(self, affiliate_id: str | None) -> RateOptimization:
        """Real reservation (RI) + savings-plan recommendations from Azure."""
        targets = self._targets(affiliate_id)
        recommendations: list[ReservationRecommendation] = []
        by_service: dict[str, float] = {}
        savings_plan_commitment = 0.0
        savings_to_date = 0.0
        for sid, tenant in targets:
            try:
                for rec in self.client.reservation_recommendations(sid, tenant_id=tenant):
                    service = _RESERVATION_SERVICE.get(rec["resource_type"], _spaced(rec["resource_type"]))
                    by_service[service] = by_service.get(service, 0.0) + rec["monthly_savings"]
                    recommendations.append(
                        ReservationRecommendation(
                            affiliate_id=affiliate_id or sid,
                            service=service,
                            sku=rec["sku"] or service,
                            term=rec["term"],
                            recommended_quantity=rec["recommended_quantity"],
                            monthly_savings=rec["monthly_savings"],
                            savings_pct=rec["savings_pct"],
                        )
                    )
                sp = self.client.savings_plan_recommendations(sid, tenant_id=tenant)
                savings_plan_commitment += sp.get("commitment", 0.0)
                savings_to_date += self.client.realized_commitment_value(sid, self._months, tenant_id=tenant)
            except Exception as exc:  # pragma: no cover - permission/transient
                logger.warning("rate_optimization: subscription %s failed: %s", sid, exc)

        # Existing commitments (reservations + savings plans) per distinct tenant.
        active_plans = 0
        for tenant in {t for _, t in targets}:
            try:
                inv = self.client.commitment_inventory(tenant_id=tenant or None)
                active_plans += inv.get("reservations", 0) + inv.get("savings_plans", 0)
            except Exception as exc:  # pragma: no cover
                logger.warning("rate_optimization: commitment inventory failed: %s", exc)

        by_service_list = sorted(
            (SavingsByService(service=s, potential_savings=round(v, 2)) for s, v in by_service.items() if v),
            key=lambda x: x.potential_savings,
            reverse=True,
        )
        recommendations.sort(key=lambda x: x.monthly_savings, reverse=True)
        return RateOptimization(
            potential_reservation_savings=round(sum(by_service.values()), 2),
            savings_plan_commitment=round(savings_plan_commitment, 2),
            savings_to_date=round(savings_to_date, 2),
            active_savings_plans=active_plans,
            by_service=by_service_list,
            recommendations=recommendations[:25],
        )

    def prepayment(self) -> PrepaymentSummary:
        balances = self.macc_balances()
        total = sum(b.commitment_amount for b in balances)
        utilized = sum(b.consumed_amount for b in balances)
        return PrepaymentSummary(
            macc_total_balance=round(total, 2),
            macc_utilized=round(utilized, 2),
            commit_to_consume=round(sum(b.remaining_balance for b in balances), 2),
            azure_prepayment=0.0,
        )

    def offer_mix(self) -> list[OfferMixSlice]:
        totals: dict[str, float] = {}
        targets = self._targets(None)
        for sid, tenant in targets:
            try:
                for row in self.client.dimension_totals(sid, "PricingModel", self._months, tenant_id=tenant):
                    totals[row["key"]] = totals.get(row["key"], 0.0) + row["cost"]
            except Exception as exc:  # pragma: no cover
                logger.warning("offer_mix: subscription %s failed: %s", sid, exc)
        sub_count = len(targets)
        return [
            OfferMixSlice(name=name, invoiced_usage=round(cost, 2), subscriptions=sub_count)
            for name, cost in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
            if cost
        ]

    def _external_copilot(self, affiliate_id: str | None) -> dict:
        """Real GitHub + M365 Copilot seats/cost/acceptance across affiliates."""
        defs = self._affiliate_defs()
        if affiliate_id is not None:
            defs = [d for d in defs if d["affiliate_id"] == affiliate_id]
        rows: list[AiConsumptionRow] = []
        gh_seats = m365_seats = 0
        gh_cost = m365_cost = 0.0
        acc_weighted = acc_seats = 0.0
        seen_orgs: set[str] = set()
        seen_tenants: dict[str, list[dict]] = {}
        for d in defs:
            # GitHub Copilot (per org, once).
            for org in d.get("github_orgs", []):
                if org in seen_orgs:
                    continue
                seen_orgs.add(org)
                info = self.github.copilot_summary(org)
                if info.get("seats"):
                    gh_seats += info["seats"]
                    gh_cost += info["cost"]
                    acc_weighted += info["acceptance_pct"] * info["seats"]
                    acc_seats += info["seats"]
                    rows.append(
                        AiConsumptionRow(
                            affiliate_id=d["affiliate_id"],
                            source="GitHub Copilot",
                            origin=f"GitHub billing API (org {org})",
                            metric_type="seats",
                            quantity=float(info["seats"]),
                            cost=info["cost"],
                        )
                    )
            # M365 Copilot seats from Graph SKUs (per tenant, once).
            tenant = d.get("tenant_id") or ""
            if tenant not in seen_tenants:
                try:
                    seen_tenants[tenant] = self.graph.subscribed_skus(tenant or None)
                except Exception:  # pragma: no cover
                    seen_tenants[tenant] = []
            seats = sum(s["assigned"] for s in seen_tenants[tenant] if "copilot" in s["sku"].lower())
            if seats:
                cost = round(seats * self.settings.m365_copilot_seat_cost, 2)
                m365_seats += seats
                m365_cost += cost
                rows.append(
                    AiConsumptionRow(
                        affiliate_id=d["affiliate_id"],
                        source="M365 Copilot",
                        origin="Microsoft Graph subscribedSkus",
                        metric_type="seats",
                        quantity=float(seats),
                        cost=cost,
                    )
                )
        acceptance = round(acc_weighted / acc_seats, 1) if acc_seats else 0.0
        return {
            "rows": rows,
            "seats": gh_seats + m365_seats,
            "github_cost": round(gh_cost, 2),
            "m365_cost": round(m365_cost, 2),
            "acceptance_pct": acceptance,
        }

    def ai_consumption(self, affiliate_id: str | None) -> AiConsumption:
        targets = self._targets(affiliate_id)
        rows: list[AiConsumptionRow] = []
        by_source: dict[str, float] = {}
        ai_resources: list[tuple[str, str]] = []  # (resource_id, tenant) for token lookup
        for sid, tenant in targets:
            try:
                for row in self.client.resource_costs(sid, self._months, tenant_id=tenant):
                    if not is_ai_service(row["service_name"]):
                        continue
                    cost = round(row["cost_usd"], 2)
                    by_source[row["service_name"]] = by_source.get(row["service_name"], 0.0) + cost
                    rid = row["resource_id"] or ""
                    if rid and "cognitiveservices" in rid.lower():
                        ai_resources.append((rid, tenant))
                    rows.append(
                        AiConsumptionRow(
                            affiliate_id=affiliate_id or sid,
                            source=row["service_name"],
                            origin="Azure Cost Management (FOCUS)",
                            metric_type="cost",
                            quantity=0.0,
                            cost=cost,
                        )
                    )
            except Exception as exc:  # pragma: no cover
                logger.warning("ai_consumption: subscription %s failed: %s", sid, exc)

        # Real Azure OpenAI token counts via Azure Monitor (top resources by cost).
        monthly_tokens: dict[str, float] = {}
        for resource_id, tenant in sorted(ai_resources, key=lambda x: x[0])[:15]:
            try:
                for month, tokens in self.client.monitor_token_totals(resource_id, self._months, tenant_id=tenant).items():
                    monthly_tokens[month] = monthly_tokens.get(month, 0.0) + tokens
            except Exception as exc:  # pragma: no cover
                logger.info("token lookup for %s failed: %s", resource_id, exc)
        total_tokens = round(sum(monthly_tokens.values()), 0)

        # Per-deployment tokens-per-minute (last 24h) via Azure Monitor, split by
        # ModelDeploymentName, for the top Foundry/Azure OpenAI accounts by cost.
        deployments: list[DeploymentTpm] = []
        seen_accounts: set[str] = set()
        for resource_id, tenant in sorted(ai_resources, key=lambda x: x[0])[:15]:
            account = _parse_resource_id(resource_id)["resource_name"] or resource_id
            if account in seen_accounts:
                continue
            seen_accounts.add(account)
            try:
                tpm_rows = self.client.monitor_deployment_tpm(resource_id, hours=24, tenant_id=tenant)
                if not tpm_rows:
                    continue
                models = self.client.list_deployments(resource_id, tenant_id=tenant)
                for d in tpm_rows:
                    deployments.append(
                        DeploymentTpm(
                            affiliate_id=affiliate_id or "",
                            account=account,
                            deployment=d["deployment"],
                            model=models.get(d["deployment"], ""),
                            total_tokens=d["total_tokens"],
                            avg_tpm=d["avg_tpm"],
                            peak_tpm=d["peak_tpm"],
                            window_hours=24,
                        )
                    )
            except Exception as exc:  # pragma: no cover - metric/permission
                logger.info("deployment TPM for %s failed: %s", resource_id, exc)
        deployments.sort(key=lambda d: d.peak_tpm, reverse=True)

        # External Copilot seats (GitHub + M365).
        ext = self._external_copilot(affiliate_id)
        rows.extend(ext["rows"])
        for r in ext["rows"]:
            by_source[r.source] = by_source.get(r.source, 0.0) + r.cost

        total_ai_cost = round(sum(r.cost for r in rows), 2)
        summary = sorted(
            (
                AiSourceSummary(
                    source=s,
                    cost=round(c, 2),
                    quantity=round(sum(r.quantity for r in rows if r.source == s), 0),
                    metric_type=next((r.metric_type for r in rows if r.source == s), "cost"),
                )
                for s, c in by_source.items()
            ),
            key=lambda x: x.cost,
            reverse=True,
        )
        cost_trend = self.cost_summary(affiliate_id).trend
        total_all = sum(p.cost for p in cost_trend) or 1.0
        azure_ai_cost = round(sum(r.cost for r in rows if r.metric_type == "cost"), 2)
        share = azure_ai_cost / total_all if total_all else 0.0
        trend = [
            AiTrendPoint(month=p.month, tokens=round(monthly_tokens.get(p.month, 0.0), 0), cost=round(p.cost * share, 2))
            for p in cost_trend
        ]
        return AiConsumption(
            total_ai_cost=total_ai_cost,
            total_tokens=total_tokens,
            copilot_seats=int(ext["seats"]),
            avg_acceptance_pct=ext["acceptance_pct"],
            by_source=summary,
            trend=trend,
            rows=sorted(rows, key=lambda x: x.cost, reverse=True)[:40],
            deployments=deployments,
        )

    def tco(self, affiliate_id: str | None) -> TcoSummary:
        costs = self.cost_summary(affiliate_id)
        azure = costs.total_cost_mtd
        # Monthly license spend from real seat counts x (list/negotiated) price.
        license_monthly = round(sum(l.assigned * l.unit_cost for l in self.licenses(affiliate_id)), 2)
        external_copilot = self._external_copilot(affiliate_id)
        # M365 Copilot seats are already counted in license_cost (Entra SKUs); only
        # GitHub Copilot is truly external (billed outside Azure and Entra).
        external_cost = external_copilot["github_cost"]
        by_source = [
            TcoSourceSlice(source="Azure", cost=round(azure, 2)),
            TcoSourceSlice(source="Licenses", cost=license_monthly),
            TcoSourceSlice(source="Copilot (external)", cost=external_cost),
        ]
        trend = [
            TcoTrendPoint(
                month=p.month, azure=round(p.cost, 2), licenses=license_monthly, copilot_external=external_cost
            )
            for p in costs.trend
        ]
        return TcoSummary(
            total=round(azure + license_monthly + external_cost, 2),
            azure_cost=round(azure, 2),
            license_cost=license_monthly,
            external_copilot_cost=external_cost,
            by_source=by_source,
            trend=trend,
        )


def _num(value: object) -> float:
    try:
        return float(value or 0.0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _min_date(a: date | None, b: date | None) -> date | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _max_date(a: date | None, b: date | None) -> date | None:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)
