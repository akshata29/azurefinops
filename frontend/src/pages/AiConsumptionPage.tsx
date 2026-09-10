import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { Badge } from '../components/Badge';
import { AffiliateFilter } from '../components/AffiliateFilter';
import { aiApi } from '../api/client';
import { formatCurrency, formatMonth, formatNumber, formatPercent } from '../lib/format';
import { CHART, SERIES, tooltipStyle } from '../lib/theme';

const originTone: Record<string, 'blue' | 'green' | 'amber' | 'slate'> = {
  'FOCUS cost + Azure Monitor tokens': 'blue',
  'Azure (SCU meters in FOCUS)': 'blue',
  'GitHub billing + metrics API': 'green',
  'M365 commerce + Graph usage': 'amber',
};

export function AiConsumptionPage() {
  const [affiliate, setAffiliate] = useState('');
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ai', affiliate],
    queryFn: () => aiApi.get(affiliate || undefined),
  });

  return (
    <Layout
      title="AI & Copilot Consumption"
      subtitle="Azure OpenAI / Foundry tokens, GitHub & M365 Copilot, Security/Fabric"
      actions={<AffiliateFilter value={affiliate} onChange={setAffiliate} />}
    >
      {isLoading && <Spinner label="Loading AI consumption…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Total AI/Copilot cost" value={formatCurrency(data.total_ai_cost, data.currency, true)} sub="per month" accent="blue" />
            <KpiCard label="Tokens (Azure OpenAI/Foundry)" value={formatNumber(data.total_tokens, true)} accent="emerald" />
            <KpiCard label="Copilot seats" value={formatNumber(data.copilot_seats)} sub="GitHub + M365" accent="blue" />
            <KpiCard label="Avg acceptance" value={formatPercent(data.avg_acceptance_pct)} sub="GitHub Copilot" accent="emerald" />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard title="Token consumption trend" subtitle="Azure OpenAI + Foundry (monthly)" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={data.trend} margin={{ left: 4, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="tokFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.primary} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={CHART.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12, fill: CHART.slate }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => formatNumber(v, true)} tick={{ fontSize: 12, fill: CHART.slate }} axisLine={false} tickLine={false} width={56} />
                  <Tooltip formatter={(v: number) => formatNumber(v)} labelFormatter={formatMonth} contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="tokens" stroke={CHART.primary} strokeWidth={2} fill="url(#tokFill)" name="Tokens" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Cost by source" subtitle="Where AI spend lands">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.by_source} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 11, fill: CHART.slate }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="source" width={110} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                    {data.by_source.map((_, i) => (
                      <Cell key={i} fill={SERIES[i % SERIES.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="card">
            <div className="border-b border-slate-100 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Consumption detail</h3>
              <p className="text-xs text-slate-400">Data origin shows how each source is collected (Q5)</p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="th">Affiliate</th>
                    <th className="th">Source</th>
                    <th className="th">Data origin</th>
                    <th className="th text-right">Quantity</th>
                    <th className="th">Unit</th>
                    <th className="th text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {data.rows.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50/60">
                      <td className="td font-mono text-xs text-slate-500">{row.affiliate_id}</td>
                      <td className="td font-medium text-slate-900">{row.source}</td>
                      <td className="td"><Badge tone={originTone[row.origin] ?? 'slate'}>{row.origin}</Badge></td>
                      <td className="td text-right">{formatNumber(row.quantity)}</td>
                      <td className="td text-slate-500">{row.metric_type}</td>
                      <td className="td text-right font-semibold text-slate-900">{formatCurrency(row.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
