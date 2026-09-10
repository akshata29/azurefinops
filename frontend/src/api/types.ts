// Shared API types — mirror the backend Pydantic models.

export type AgreementType = 'EA' | 'MCA';
export type MaccStatus = 'Active' | 'Expired' | 'Complete';
export type OnboardingStatus = 'Active' | 'Onboarding' | 'Error' | 'Paused';

export interface Affiliate {
  affiliate_id: string;
  name: string;
  tenant_id: string;
  agreement_type: AgreementType;
  billing_account: string;
  billing_profile: string | null;
  status: OnboardingStatus;
  onboarded_on: string;
  last_data_refresh: string | null;
}

export interface MaccBalance {
  affiliate_id: string;
  affiliate_name: string;
  commitment_amount: number;
  remaining_balance: number;
  consumed_amount: number;
  percent_consumed: number;
  currency: string;
  start_date: string;
  end_date: string;
  days_remaining: number;
  status: MaccStatus;
  projected_exhaustion_date: string | null;
  on_track: boolean;
}

export interface MaccEvent {
  affiliate_id: string;
  event_date: string;
  description: string;
  charges: number;
  remaining_after: number;
  currency: string;
}

export interface MaccTrendPoint {
  month: string;
  remaining_balance: number;
  consumed_cumulative: number;
}

export interface MaccDetail {
  balance: MaccBalance;
  trend: MaccTrendPoint[];
  events: MaccEvent[];
}

export interface CostPoint {
  month: string;
  affiliate_id: string;
  cost: number;
  amortized_cost: number;
  currency: string;
}

export interface CostByService {
  service: string;
  cost: number;
}

export interface CostSummary {
  total_cost_mtd: number;
  total_cost_last_month: number;
  mom_change_pct: number;
  currency: string;
  trend: CostPoint[];
  by_service: CostByService[];
}

export interface License {
  affiliate_id: string;
  product: string;
  sku: string;
  assigned: number;
  consumed: number;
  unit_cost: number;
  currency: string;
  renewal_date: string | null;
}

export interface ResourceCost {
  affiliate_id: string;
  resource_name: string;
  resource_group: string;
  service_category: string;
  service_name: string;
  resource_type: string;
  region: string;
  cost: number;
  currency: string;
}

export interface BreakdownNode {
  name: string;
  level: number; // 1=category, 2=service, 3=resourceType, 4=resource
  cost: number;
  pct_of_parent: number;
  children: BreakdownNode[];
}

export interface AffiliateCostDetail {
  affiliate_id: string;
  affiliate_name: string;
  total_cost: number;
  currency: string;
  resource_count: number;
  breakdown: BreakdownNode[];
  top_resources: ResourceCost[];
}

// Slice A — rate optimization
export interface ReservationRecommendation {
  affiliate_id: string;
  service: string;
  sku: string;
  term: string;
  recommended_quantity: number;
  monthly_savings: number;
  savings_pct: number;
  currency: string;
}
export interface SavingsByService {
  service: string;
  potential_savings: number;
}
export interface RateOptimization {
  potential_reservation_savings: number;
  savings_plan_commitment: number;
  savings_to_date: number;
  active_savings_plans: number;
  currency: string;
  by_service: SavingsByService[];
  recommendations: ReservationRecommendation[];
}

// Slice B — prepayment & offer mix
export interface PrepaymentSummary {
  macc_total_balance: number;
  macc_utilized: number;
  commit_to_consume: number;
  azure_prepayment: number;
  currency: string;
}
export interface OfferMixSlice {
  name: string;
  invoiced_usage: number;
  subscriptions: number;
}

// Slice C — billing hierarchy
export interface HierarchyNode {
  name: string;
  node_type: string;
  identifier: string | null;
  cost: number;
  pct_of_parent: number;
  children: HierarchyNode[];
}
export interface AffiliateHierarchy {
  affiliate_id: string;
  affiliate_name: string;
  total_cost: number;
  currency: string;
  root: HierarchyNode;
}

// Slice D — AI & Copilot
export interface AiConsumptionRow {
  affiliate_id: string;
  source: string;
  origin: string;
  metric_type: string;
  quantity: number;
  cost: number;
  currency: string;
}
export interface AiSourceSummary {
  source: string;
  cost: number;
  quantity: number;
  metric_type: string;
}
export interface AiTrendPoint {
  month: string;
  tokens: number;
  cost: number;
}
export interface AiConsumption {
  total_ai_cost: number;
  total_tokens: number;
  copilot_seats: number;
  avg_acceptance_pct: number;
  currency: string;
  by_source: AiSourceSummary[];
  trend: AiTrendPoint[];
  rows: AiConsumptionRow[];
}

// Slice E — TCO
export interface TcoSourceSlice {
  source: string;
  cost: number;
}
export interface TcoTrendPoint {
  month: string;
  azure: number;
  licenses: number;
  copilot_external: number;
}
export interface TcoSummary {
  total: number;
  azure_cost: number;
  license_cost: number;
  external_copilot_cost: number;
  currency: string;
  by_source: TcoSourceSlice[];
  trend: TcoTrendPoint[];
}

export interface PortfolioSummary {
  affiliate_count: number;
  active_count: number;
  total_commitment: number;
  total_remaining: number;
  total_consumed: number;
  percent_consumed: number;
  total_cost_mtd: number;
  at_risk_count: number;
  currency: string;
  generated_at: string;
}
