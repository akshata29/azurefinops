// Shared visual theme tokens so charts/colors stay consistent across pages.
export const CHART = {
  primary: '#2563eb', // brand-600
  primaryDark: '#1d4ed8', // brand-700
  primaryLight: '#60a5fa', // brand-400
  accent: '#10b981', // emerald-500
  amber: '#f59e0b',
  slate: '#94a3b8',
  grid: '#eef2f7',
};

// Ordered categorical palette — brand-aligned (blues → teal → emerald → amber),
// no clashing purples, so donuts/bars stay consistent with the rest of the UI.
export const SERIES = [
  '#1d4ed8',
  '#2563eb',
  '#3b82f6',
  '#60a5fa',
  '#93c5fd',
  '#0ea5e9',
  '#14b8a6',
  '#10b981',
  '#34d399',
  '#f59e0b',
];

export const tooltipStyle = {
  borderRadius: 12,
  border: '1px solid #e2e8f0',
  fontSize: 12,
  boxShadow: '0 4px 12px rgba(16,24,40,.08)',
};
