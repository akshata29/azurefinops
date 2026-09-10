"""Slices B & C — prepayment / offer mix, and billing hierarchy drill."""
from __future__ import annotations

from app.data.demo import build_affiliates, build_macc_balance, build_cost_summary, _rng
from app.data.resources import build_resources
from app.models import (
    AffiliateHierarchy,
    HierarchyNode,
    OfferMixSlice,
    PrepaymentSummary,
)


# --- Slice B ---------------------------------------------------------------
def build_prepayment() -> PrepaymentSummary:
    balances = [build_macc_balance(a) for a in build_affiliates()]
    total = sum(b.commitment_amount for b in balances)
    utilized = sum(b.consumed_amount for b in balances)
    r = _rng("prepay")
    return PrepaymentSummary(
        macc_total_balance=round(total, 2),
        macc_utilized=round(utilized, 2),
        commit_to_consume=round(total * r.uniform(0.02, 0.06), 2),
        azure_prepayment=round(total * r.uniform(0.03, 0.08), 2),
    )


def build_offer_mix() -> list[OfferMixSlice]:
    affiliates = build_affiliates()
    total_cost = build_cost_summary(None).total_cost_mtd
    # Distribute invoiced usage across pricing/offer types.
    weights = {
        "EA": 0.34,
        "MCA": 0.28,
        "CSP": 0.12,
        "Reservation": 0.14,
        "Savings plan": 0.08,
        "On-demand": 0.04,
    }
    ea = sum(1 for a in affiliates if a.agreement_type.value == "EA")
    mca = len(affiliates) - ea
    subs = {
        "EA": ea * 6,
        "MCA": mca * 5,
        "CSP": 3,
        "Reservation": 0,
        "Savings plan": 0,
        "On-demand": len(affiliates) * 2,
    }
    return [
        OfferMixSlice(name=k, invoiced_usage=round(total_cost * 12 * w, 2), subscriptions=subs[k])
        for k, w in weights.items()
    ]


# --- Slice C ---------------------------------------------------------------
def _node(name: str, node_type: str, cost: float, identifier: str | None = None) -> HierarchyNode:
    return HierarchyNode(name=name, node_type=node_type, cost=cost, identifier=identifier)


def build_hierarchy(affiliate_id: str) -> AffiliateHierarchy | None:
    aff = next((a for a in build_affiliates() if a.affiliate_id == affiliate_id), None)
    if aff is None:
        return None
    resources = build_resources(affiliate_id)
    total = sum(rc.cost for rc in resources)

    # billingProfile -> invoiceSection (prod/nonprod) -> subscription (rg-prefix) -> resourceGroup -> resource
    root = _node(aff.name, "billingProfile", total, aff.billing_profile or aff.billing_account)

    def section_for(rg: str) -> str:
        return "Production" if "prod" in rg else "Non-production"

    def subscription_for(rg: str) -> str:
        # Group resource groups into a synthetic subscription by environment token.
        token = rg.split("-")[1] if "-" in rg else "core"
        return f"sub-{token}"

    for rc in resources:
        section_name = section_for(rc.resource_group)
        section = next((c for c in root.children if c.name == section_name), None)
        if section is None:
            section = _node(section_name, "invoiceSection", 0.0)
            root.children.append(section)
        section.cost += rc.cost

        sub_name = subscription_for(rc.resource_group)
        sub = next((c for c in section.children if c.name == sub_name), None)
        if sub is None:
            sub = _node(sub_name, "subscription", 0.0, identifier=f"{_rng(sub_name).randint(10000000, 99999999):08x}")
            section.children.append(sub)
        sub.cost += rc.cost

        rg = next((c for c in sub.children if c.name == rc.resource_group), None)
        if rg is None:
            rg = _node(rc.resource_group, "resourceGroup", 0.0)
            sub.children.append(rg)
        rg.cost += rc.cost

        rg.children.append(_node(rc.resource_name, "resource", rc.cost, identifier=rc.region))

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
    return AffiliateHierarchy(
        affiliate_id=affiliate_id,
        affiliate_name=aff.name,
        total_cost=round(total, 2),
        root=root,
    )
