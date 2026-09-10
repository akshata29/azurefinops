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
import { AffiliateFilter } from '../components/AffiliateFilter';
import { costsApi } from '../api/client';
import { formatCurrency, formatMonth, formatPercent } from '../lib/format';

export function CostsPage() {
  const [affiliate, setAffiliate] = useState('');
  const { data, isLoading, isError } = useQuery({
    queryKey: ['costs', affiliate],
    queryFn: () => costsApi.summary(affiliate || undefined),
  });

  return (
    <Layout
      title="Cost & Usage"
      subtitle="FOCUS cost data — actual vs. amortized"
      actions={<AffiliateFilter value={affiliate} onChange={setAffiliate} />}
    >
      {isLoading && <Spinner label="Loading costs…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCard label="Cost month-to-date" value={formatCurrency(data.total_cost_mtd, data.currency)} accent="blue" />
            <KpiCard label="Last full month" value={formatCurrency(data.total_cost_last_month, data.currency)} accent="emerald" />
            <KpiCard
              label="Month-over-month"
              value={formatPercent(Math.abs(data.mom_change_pct))}
              delta={data.mom_change_pct}
              deltaGoodWhenUp={false}
              accent={data.mom_change_pct >= 0 ? 'amber' : 'emerald'}
            />
          </div>

          <ChartCard title="Actual vs. amortized cost" subtitle="Monthly, aggregated across affiliates">
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={data.trend} margin={{ left: 4, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="actual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2563eb" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={64} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} labelFormatter={formatMonth} contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                <Area type="monotone" dataKey="cost" name="Actual" stroke="#2563eb" strokeWidth={2} fill="url(#actual)" />
                <Area type="monotone" dataKey="amortized_cost" name="Amortized" stroke="#94a3b8" strokeWidth={2} strokeDasharray="4 3" fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Cost by service" subtitle="Top services by spend">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={data.by_service} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                <XAxis type="number" tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="service" width={140} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                  {data.by_service.map((_, i) => (
                    <Cell key={i} fill={i < 3 ? '#1d4ed8' : '#60a5fa'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}
    </Layout>
  );
}
