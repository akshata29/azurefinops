import { useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from 'recharts';
import { ArrowLeftIcon } from '@heroicons/react/20/solid';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { BreakdownTree } from '../components/BreakdownTree';
import { affiliatesApi, maccApi } from '../api/client';
import { formatCurrency, formatNumber } from '../lib/format';
import { SERIES, tooltipStyle } from '../lib/theme';

export function AffiliateDetailPage() {
  const { id = '' } = useParams();
  const detail = useQuery({
    queryKey: ['affiliate', id, 'breakdown'],
    queryFn: () => affiliatesApi.breakdown(id),
    enabled: !!id,
  });
  const macc = useQuery({
    queryKey: ['macc', 'detail', id],
    queryFn: () => maccApi.detail(id),
    enabled: !!id,
  });

  const categoryData = useMemo(
    () =>
      (detail.data?.breakdown ?? []).map((c) => ({ name: c.name, value: c.cost })),
    [detail.data],
  );

  return (
    <Layout
      title={detail.data?.affiliate_name ?? 'Affiliate'}
      subtitle="Resource-level cost drill-down · ServiceCategory → Service → ResourceType → Resource"
    >
      <Link
        to="/affiliates"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"
      >
        <ArrowLeftIcon className="h-4 w-4" /> Back to affiliates
      </Link>

      {(detail.isLoading || macc.isLoading) && <Spinner label="Loading affiliate detail…" />}
      {detail.isError && <ErrorState />}

      {detail.data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total resource cost"
              value={formatCurrency(detail.data.total_cost, detail.data.currency, true)}
              accent="blue"
            />
            <KpiCard label="Resources" value={formatNumber(detail.data.resource_count)} accent="emerald" />
            <KpiCard
              label="Service categories"
              value={formatNumber(detail.data.breakdown.length)}
              accent="blue"
            />
            {macc.data && (
              <KpiCard
                label="MACC remaining"
                value={formatCurrency(macc.data.balance.remaining_balance, macc.data.balance.currency, true)}
                sub={`${macc.data.balance.percent_consumed.toFixed(1)}% consumed`}
                accent={macc.data.balance.on_track ? 'emerald' : 'amber'}
              />
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard
              title="Cost breakdown"
              subtitle="Expand to drill from category down to individual resource"
              className="lg:col-span-2"
            >
              <div className="mb-2 flex items-center justify-end gap-6 pr-3 text-[10px] uppercase tracking-wide text-slate-400">
                <span className="hidden md:inline">Share</span>
                <span className="w-14 text-right">% parent</span>
                <span className="w-24 text-right">Cost</span>
              </div>
              <div className="max-h-[520px] overflow-y-auto">
                <BreakdownTree nodes={detail.data.breakdown} />
              </div>
            </ChartCard>

            <ChartCard title="By service category" subtitle="Share of total cost">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={SERIES[i % SERIES.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="card">
            <div className="border-b border-slate-100 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Top resources</h3>
              <p className="text-xs text-slate-400">Highest-cost individual resources this month</p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="th">Resource</th>
                    <th className="th">Resource group</th>
                    <th className="th">Service</th>
                    <th className="th">Type</th>
                    <th className="th">Region</th>
                    <th className="th text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {detail.data.top_resources.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50/60">
                      <td className="td font-medium text-slate-900">{r.resource_name}</td>
                      <td className="td font-mono text-xs text-slate-500">{r.resource_group}</td>
                      <td className="td">{r.service_name}</td>
                      <td className="td text-slate-500">{r.resource_type}</td>
                      <td className="td font-mono text-xs text-slate-500">{r.region}</td>
                      <td className="td text-right font-semibold text-slate-900">{formatCurrency(r.cost)}</td>
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
