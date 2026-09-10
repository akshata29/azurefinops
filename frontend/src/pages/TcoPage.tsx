import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { AffiliateFilter } from '../components/AffiliateFilter';
import { tcoApi } from '../api/client';
import { formatCurrency, formatMonth, formatPercent } from '../lib/format';
import { CHART, tooltipStyle } from '../lib/theme';

const SOURCE_COLORS: Record<string, string> = {
  Azure: '#2563eb',
  Licenses: '#10b981',
  'Copilot (external)': '#f59e0b',
};

export function TcoPage() {
  const [affiliate, setAffiliate] = useState('');
  const { data, isLoading, isError } = useQuery({
    queryKey: ['tco', affiliate],
    queryFn: () => tcoApi.get(affiliate || undefined),
  });

  const pie = (data?.by_source ?? []).map((s) => ({ name: s.source, value: s.cost }));

  return (
    <Layout
      title="Total Cost of Ownership"
      subtitle="Azure + external licenses + external Copilot — unified monthly view"
      actions={<AffiliateFilter value={affiliate} onChange={setAffiliate} />}
    >
      {isLoading && <Spinner label="Loading TCO…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Total cost of ownership" value={formatCurrency(data.total, data.currency, true)} sub="per month" accent="blue" />
            <KpiCard
              label="Azure (FOCUS)"
              value={formatCurrency(data.azure_cost, data.currency, true)}
              sub={formatPercent((data.azure_cost / data.total) * 100)}
              accent="blue"
            />
            <KpiCard
              label="External licenses"
              value={formatCurrency(data.license_cost, data.currency, true)}
              sub={formatPercent((data.license_cost / data.total) * 100)}
              accent="emerald"
            />
            <KpiCard
              label="External Copilot"
              value={formatCurrency(data.external_copilot_cost, data.currency, true)}
              sub={formatPercent((data.external_copilot_cost / data.total) * 100)}
              accent="amber"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard title="Monthly TCO trend" subtitle="Stacked by source" className="lg:col-span-2">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={data.trend} margin={{ left: 4, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12, fill: CHART.slate }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 12, fill: CHART.slate }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} labelFormatter={formatMonth} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="azure" stackId="a" fill={SOURCE_COLORS['Azure']} name="Azure" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="licenses" stackId="a" fill={SOURCE_COLORS['Licenses']} name="Licenses" />
                  <Bar dataKey="copilot_external" stackId="a" fill={SOURCE_COLORS['Copilot (external)']} name="Copilot (external)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Cost mix" subtitle="Share of total">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                    {pie.map((s, i) => (
                      <Cell key={i} fill={SOURCE_COLORS[s.name] ?? '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="rounded-lg border border-brand-100 bg-brand-50 p-4 text-xs text-brand-700">
            Azure cost (FOCUS) already includes Azure OpenAI, Foundry, Security &amp; Fabric Copilot, so those are not
            double-counted. Only license spend and Copilot seats billed <strong>outside</strong> Azure (M365, GitHub) are added on top.
          </div>
        </div>
      )}
    </Layout>
  );
}
