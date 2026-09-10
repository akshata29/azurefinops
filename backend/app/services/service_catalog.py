"""Map Azure Cost Management ``ServiceName`` values to a FOCUS-style category.

The legacy Cost Management dimensions expose ``ServiceName`` but not the FOCUS
``ServiceCategory`` column, so we classify service names into the same top-level
buckets the demo data uses. Unknown services fall back to ``"Other"`` — real,
just uncategorised — rather than being dropped.
"""
from __future__ import annotations

# Substring -> category. First match wins; order matters (specific before broad).
_RULES: list[tuple[str, str]] = [
    ("virtual machine", "Compute"),
    ("virtual machines", "Compute"),
    ("kubernetes", "Compute"),
    ("container", "Compute"),
    ("app service", "Compute"),
    ("functions", "Compute"),
    ("batch", "Compute"),
    ("service fabric", "Compute"),
    ("cloud services", "Compute"),
    ("storage", "Storage"),
    ("backup", "Storage"),
    ("site recovery", "Storage"),
    ("netapp", "Storage"),
    ("hpc cache", "Storage"),
    ("sql", "Databases"),
    ("cosmos", "Databases"),
    ("database", "Databases"),
    ("postgresql", "Databases"),
    ("mysql", "Databases"),
    ("mariadb", "Databases"),
    ("redis", "Databases"),
    ("cache for redis", "Databases"),
    ("bandwidth", "Networking"),
    ("network", "Networking"),
    ("load balancer", "Networking"),
    ("application gateway", "Networking"),
    ("vpn", "Networking"),
    ("expressroute", "Networking"),
    ("front door", "Networking"),
    ("cdn", "Networking"),
    ("dns", "Networking"),
    ("firewall", "Networking"),
    ("traffic manager", "Networking"),
    ("openai", "AI + ML"),
    ("foundry", "AI + ML"),
    ("bing", "AI + ML"),
    ("cognitive", "AI + ML"),
    ("machine learning", "AI + ML"),
    ("ai foundry", "AI + ML"),
    ("ai services", "AI + ML"),
    ("ai studio", "AI + ML"),
    ("azure ai", "AI + ML"),
    ("content safety", "AI + ML"),
    ("document intelligence", "AI + ML"),
    ("form recognizer", "AI + ML"),
    ("translator", "AI + ML"),
    ("language", "AI + ML"),
    ("speech", "AI + ML"),
    ("vision", "AI + ML"),
    ("immersive reader", "AI + ML"),
    ("personalizer", "AI + ML"),
    ("anomaly detector", "AI + ML"),
    ("metrics advisor", "AI + ML"),
    ("video indexer", "AI + ML"),
    ("bot service", "AI + ML"),
    ("search", "AI + ML"),
    ("data explorer", "Analytics"),
    ("synapse", "Analytics"),
    ("databricks", "Analytics"),
    ("data factory", "Analytics"),
    ("event hub", "Analytics"),
    ("stream analytics", "Analytics"),
    ("hdinsight", "Analytics"),
    ("data lake", "Analytics"),
    ("power bi", "Analytics"),
    ("fabric", "Analytics"),
    ("key vault", "Security"),
    ("defender", "Security"),
    ("sentinel", "Security"),
    ("security", "Security"),
    ("active directory", "Security"),
    ("entra", "Security"),
    ("monitor", "Management"),
    ("log analytics", "Management"),
    ("automation", "Management"),
    ("advisor", "Management"),
    ("policy", "Management"),
    ("logic apps", "Integration"),
    ("api management", "Integration"),
    ("service bus", "Integration"),
    ("event grid", "Integration"),
]


def service_category(service_name: str | None) -> str:
    name = (service_name or "").lower()
    for needle, category in _RULES:
        if needle in name:
            return category
    return "Other"


# Services whose spend counts as AI / Copilot consumption.
_AI_CATEGORY = "AI + ML"


def is_ai_service(service_name: str | None) -> bool:
    return service_category(service_name) == _AI_CATEGORY
