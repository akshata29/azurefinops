"""Resource-level demo data + hierarchical cost breakdown (drill-down).

Hierarchy (4 levels) mirrors FOCUS columns:
  ServiceCategory (L1) -> ServiceName (L2) -> ResourceType/meter (L3) -> Resource (L4)
"""
from __future__ import annotations

import random

from app.models import AffiliateCostDetail, BreakdownNode, ResourceCost
from app.data.demo import build_affiliates, _rng

# ServiceCategory -> ServiceName -> [resource types]
_CATALOG: dict[str, dict[str, list[str]]] = {
    "Compute": {
        "Virtual Machines": ["Standard_D4s_v5", "Standard_E8s_v5", "Standard_F16s_v2"],
        "Azure Kubernetes Service": ["Standard_D8s_v5 node", "Standard_B4ms node"],
        "App Service": ["P1v3 plan", "P2v3 plan"],
        "Functions": ["Premium EP1", "Consumption"],
    },
    "Storage": {
        "Blob Storage": ["Hot LRS", "Cool LRS", "Archive"],
        "Managed Disks": ["Premium SSD P30", "Standard SSD E20"],
        "Files": ["Premium share"],
    },
    "Databases": {
        "Azure SQL Database": ["Business Critical vCore", "General Purpose vCore"],
        "Cosmos DB": ["Provisioned RU/s", "Serverless"],
        "PostgreSQL Flexible": ["General Purpose D4s"],
    },
    "Networking": {
        "Application Gateway": ["WAF_v2 capacity unit"],
        "VPN Gateway": ["VpnGw2"],
        "Bandwidth": ["Inter-region egress"],
    },
    "AI + ML": {
        "Azure OpenAI": ["gpt-4o tokens", "gpt-4o-mini tokens", "text-embedding-3"],
        "Azure AI Foundry": ["Model inference", "Agent runtime"],
        "Cognitive Services": ["Document Intelligence", "Speech"],
    },
    "Analytics": {
        "Azure Data Explorer": ["Engine D14 v2", "Ingestion"],
        "Event Hubs": ["Standard throughput unit"],
        "Synapse": ["DW200c"],
    },
    "Security": {
        "Key Vault": ["Operations", "HSM key"],
        "Defender for Cloud": ["Servers plan"],
    },
}

_REGIONS = ["eastus", "eastus2", "westus2", "westeurope", "centralus", "northeurope"]


def build_resources(affiliate_id: str) -> list[ResourceCost]:
    r = _rng(f"res:{affiliate_id}")
    rows: list[ResourceCost] = []
    # Number of resource groups per affiliate.
    rg_count = r.randint(4, 8)
    rgs = [f"rg-{r.choice(['prod', 'dev', 'qa', 'shared', 'data', 'net'])}-{i:02d}" for i in range(rg_count)]
    for category, services in _CATALOG.items():
        # Not every affiliate uses every category.
        if r.random() < 0.15:
            continue
        for service, rtypes in services.items():
            if r.random() < 0.25:
                continue
            for rtype in rtypes:
                if r.random() < 0.4:
                    continue
                n = r.randint(1, 4)
                for i in range(n):
                    base = r.uniform(400, 22000)
                    # AI + ML skews higher to make token costs visible.
                    if category == "AI + ML":
                        base *= r.uniform(1.5, 4.0)
                    rows.append(
                        ResourceCost(
                            affiliate_id=affiliate_id,
                            resource_name=f"{rtype.split()[0].lower().replace('_', '-')}-{r.choice(['app', 'svc', 'db', 'core', 'edge'])}-{i:02d}",
                            resource_group=r.choice(rgs),
                            service_category=category,
                            service_name=service,
                            resource_type=rtype,
                            region=r.choice(_REGIONS),
                            cost=round(base, 2),
                        )
                    )
    return rows


def _node(name: str, level: int, cost: float) -> BreakdownNode:
    return BreakdownNode(name=name, level=level, cost=round(cost, 2))


def build_breakdown(affiliate_id: str) -> AffiliateCostDetail:
    aff = next((a for a in build_affiliates() if a.affiliate_id == affiliate_id), None)
    resources = build_resources(affiliate_id)
    total = sum(x.cost for x in resources)

    # Nest: category -> service -> resourceType -> resource
    cat_nodes: dict[str, BreakdownNode] = {}
    for rc in resources:
        cat = cat_nodes.setdefault(rc.service_category, _node(rc.service_category, 1, 0.0))
        cat.cost += rc.cost
        svc = next((c for c in cat.children if c.name == rc.service_name), None)
        if svc is None:
            svc = _node(rc.service_name, 2, 0.0)
            cat.children.append(svc)
        svc.cost += rc.cost
        rt = next((c for c in svc.children if c.name == rc.resource_type), None)
        if rt is None:
            rt = _node(rc.resource_type, 3, 0.0)
            svc.children.append(rt)
        rt.cost += rc.cost
        rt.children.append(_node(f"{rc.resource_name} ({rc.resource_group})", 4, rc.cost))

    # Round + compute pct_of_parent + sort desc by cost at every level.
    def finalize(nodes: list[BreakdownNode], parent_cost: float) -> list[BreakdownNode]:
        nodes.sort(key=lambda n: n.cost, reverse=True)
        for n in nodes:
            n.cost = round(n.cost, 2)
            n.pct_of_parent = round(n.cost / parent_cost * 100, 1) if parent_cost else 0.0
            if n.children:
                n.children = finalize(n.children, n.cost)
        return nodes

    breakdown = finalize(list(cat_nodes.values()), total)
    top = sorted(resources, key=lambda x: x.cost, reverse=True)[:10]

    return AffiliateCostDetail(
        affiliate_id=affiliate_id,
        affiliate_name=aff.name if aff else affiliate_id,
        total_cost=round(total, 2),
        resource_count=len(resources),
        breakdown=breakdown,
        top_resources=top,
    )
