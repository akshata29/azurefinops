"""Pydantic v2 models — the API contract shared with the React dashboard."""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class AgreementType(str, Enum):
    EA = "EA"
    MCA = "MCA"


class MaccStatus(str, Enum):
    ACTIVE = "Active"
    EXPIRED = "Expired"
    COMPLETE = "Complete"


class OnboardingStatus(str, Enum):
    ACTIVE = "Active"
    ONBOARDING = "Onboarding"
    ERROR = "Error"
    PAUSED = "Paused"


# --- Affiliate registry ----------------------------------------------------
class Affiliate(BaseModel):
    affiliate_id: str = Field(..., description="Stable key used across cost/MACC/license data")
    name: str
    tenant_id: str
    agreement_type: AgreementType
    billing_account: str
    billing_profile: str | None = None
    status: OnboardingStatus = OnboardingStatus.ACTIVE
    onboarded_on: date
    last_data_refresh: date | None = None


# --- MACC ------------------------------------------------------------------
class MaccBalance(BaseModel):
    affiliate_id: str
    affiliate_name: str
    commitment_amount: float
    remaining_balance: float
    consumed_amount: float
    percent_consumed: float
    currency: str = "USD"
    start_date: date
    end_date: date
    days_remaining: int
    status: MaccStatus
    # Simple projection: does current burn rate exhaust the commitment before end_date?
    projected_exhaustion_date: date | None = None
    on_track: bool = True


class MaccEvent(BaseModel):
    affiliate_id: str
    event_date: date
    description: str
    charges: float
    remaining_after: float
    currency: str = "USD"


class MaccTrendPoint(BaseModel):
    month: str  # YYYY-MM
    remaining_balance: float
    consumed_cumulative: float


class MaccDetail(BaseModel):
    balance: MaccBalance
    trend: list[MaccTrendPoint]
    events: list[MaccEvent]


# --- Cost ------------------------------------------------------------------
class CostPoint(BaseModel):
    month: str  # YYYY-MM
    affiliate_id: str
    cost: float
    amortized_cost: float
    currency: str = "USD"


class CostByService(BaseModel):
    service: str
    cost: float


class CostSummary(BaseModel):
    total_cost_mtd: float
    total_cost_last_month: float
    mom_change_pct: float
    currency: str = "USD"
    trend: list[CostPoint]
    by_service: list[CostByService]


# --- Licenses --------------------------------------------------------------
class License(BaseModel):
    affiliate_id: str
    product: str
    sku: str
    assigned: int
    consumed: int
    unit_cost: float
    currency: str = "USD"
    renewal_date: date | None = None


# --- Resource-level breakdown (drill-down) ---------------------------------
class ResourceCost(BaseModel):
    affiliate_id: str
    resource_name: str
    resource_group: str
    service_category: str  # level 1 (e.g. Compute)
    service_name: str      # level 2 (e.g. Virtual Machines)
    resource_type: str     # level 3 (e.g. Standard_D4s_v5)
    region: str
    cost: float
    currency: str = "USD"


class BreakdownNode(BaseModel):
    name: str
    level: int  # 1=category, 2=service, 3=resourceType, 4=resource
    cost: float
    pct_of_parent: float = 100.0
    children: list["BreakdownNode"] = Field(default_factory=list)


class AffiliateCostDetail(BaseModel):
    affiliate_id: str
    affiliate_name: str
    total_cost: float
    currency: str = "USD"
    resource_count: int
    breakdown: list[BreakdownNode]  # hierarchical, level 1..4
    top_resources: list[ResourceCost]


# --- Slice A: Rate optimization (reservations & savings plans) --------------
class ReservationRecommendation(BaseModel):
    affiliate_id: str
    service: str
    sku: str
    term: str  # "1 year" | "3 years"
    recommended_quantity: int
    monthly_savings: float
    savings_pct: float
    currency: str = "USD"


class SavingsByService(BaseModel):
    service: str
    potential_savings: float


class RateOptimization(BaseModel):
    potential_reservation_savings: float
    savings_plan_commitment: float
    savings_to_date: float
    active_savings_plans: int
    currency: str = "USD"
    by_service: list[SavingsByService]
    recommendations: list[ReservationRecommendation]


# --- Slice B: Prepayment & offer mix ---------------------------------------
class PrepaymentSummary(BaseModel):
    macc_total_balance: float
    macc_utilized: float
    commit_to_consume: float
    azure_prepayment: float
    currency: str = "USD"


class OfferMixSlice(BaseModel):
    name: str  # EA | MCA | CSP | Reservation | Savings plan | On-demand
    invoiced_usage: float
    subscriptions: int


# --- Slice C: Billing hierarchy drill --------------------------------------
class HierarchyNode(BaseModel):
    name: str
    node_type: str  # billingProfile | invoiceSection | subscription | resourceGroup | resource
    identifier: str | None = None
    cost: float
    pct_of_parent: float = 100.0
    children: list["HierarchyNode"] = Field(default_factory=list)


class AffiliateHierarchy(BaseModel):
    affiliate_id: str
    affiliate_name: str
    total_cost: float
    currency: str = "USD"
    root: HierarchyNode


# --- Slice D: AI & Copilot consumption -------------------------------------
class AiConsumptionRow(BaseModel):
    affiliate_id: str
    source: str  # Azure OpenAI | Azure AI Foundry | GitHub Copilot | M365 Copilot | Security Copilot | Fabric Copilot
    origin: str  # where the data comes from (FOCUS + Monitor | GitHub API | Graph | Azure)
    metric_type: str  # tokens | seats | requests | SCU | CU
    quantity: float
    cost: float
    currency: str = "USD"


class AiSourceSummary(BaseModel):
    source: str
    cost: float
    quantity: float
    metric_type: str


class AiTrendPoint(BaseModel):
    month: str
    tokens: float
    cost: float


class AiConsumption(BaseModel):
    total_ai_cost: float
    total_tokens: float
    copilot_seats: int
    avg_acceptance_pct: float
    currency: str = "USD"
    by_source: list[AiSourceSummary]
    trend: list[AiTrendPoint]
    rows: list[AiConsumptionRow]


# --- Slice E: Total cost of ownership --------------------------------------
class TcoSourceSlice(BaseModel):
    source: str  # Azure | Licenses | Copilot (external)
    cost: float


class TcoTrendPoint(BaseModel):
    month: str
    azure: float
    licenses: float
    copilot_external: float


class TcoSummary(BaseModel):
    total: float
    azure_cost: float
    license_cost: float
    external_copilot_cost: float
    currency: str = "USD"
    by_source: list[TcoSourceSlice]
    trend: list[TcoTrendPoint]


# --- Aggregate dashboard summary ------------------------------------------
class PortfolioSummary(BaseModel):
    affiliate_count: int
    active_count: int
    total_commitment: float
    total_remaining: float
    total_consumed: float
    percent_consumed: float
    total_cost_mtd: float
    at_risk_count: int = Field(..., description="Affiliates off-track to meet/exhaust commitment")
    currency: str = "USD"
    generated_at: str
