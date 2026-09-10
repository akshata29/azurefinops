import axios from 'axios';
import type {
  Affiliate,
  AffiliateCostDetail,
  AffiliateHierarchy,
  AiConsumption,
  CostSummary,
  License,
  MaccBalance,
  MaccDetail,
  OfferMixSlice,
  PortfolioSummary,
  PrepaymentSummary,
  RateOptimization,
  ResourceCost,
  TcoSummary,
} from './types';

const http = axios.create({ baseURL: '/api/v1', timeout: 30000 });

export const summaryApi = {
  get: () => http.get<PortfolioSummary>('/summary').then((r) => r.data),
};

export const affiliatesApi = {
  list: () => http.get<Affiliate[]>('/affiliates').then((r) => r.data),
  breakdown: (affiliateId: string) =>
    http.get<AffiliateCostDetail>(`/affiliates/${affiliateId}/breakdown`).then((r) => r.data),
  resources: (affiliateId: string) =>
    http.get<ResourceCost[]>(`/affiliates/${affiliateId}/resources`).then((r) => r.data),
  hierarchy: (affiliateId: string) =>
    http.get<AffiliateHierarchy>(`/affiliates/${affiliateId}/hierarchy`).then((r) => r.data),
};

export const rateApi = {
  get: (affiliateId?: string) =>
    http
      .get<RateOptimization>('/rate-optimization', { params: affiliateId ? { affiliate_id: affiliateId } : {} })
      .then((r) => r.data),
};

export const billingApi = {
  prepayment: () => http.get<PrepaymentSummary>('/prepayment').then((r) => r.data),
  offerMix: () => http.get<OfferMixSlice[]>('/offer-mix').then((r) => r.data),
};

export const aiApi = {
  get: (affiliateId?: string) =>
    http
      .get<AiConsumption>('/ai-consumption', { params: affiliateId ? { affiliate_id: affiliateId } : {} })
      .then((r) => r.data),
};

export const tcoApi = {
  get: (affiliateId?: string) =>
    http.get<TcoSummary>('/tco', { params: affiliateId ? { affiliate_id: affiliateId } : {} }).then((r) => r.data),
};

export const maccApi = {
  balances: () => http.get<MaccBalance[]>('/macc/balances').then((r) => r.data),
  detail: (affiliateId: string) =>
    http.get<MaccDetail>(`/macc/${affiliateId}`).then((r) => r.data),
};

export const costsApi = {
  summary: (affiliateId?: string) =>
    http
      .get<CostSummary>('/costs', { params: affiliateId ? { affiliate_id: affiliateId } : {} })
      .then((r) => r.data),
};

export const licensesApi = {
  list: (affiliateId?: string) =>
    http
      .get<License[]>('/licenses', { params: affiliateId ? { affiliate_id: affiliateId } : {} })
      .then((r) => r.data),
};
