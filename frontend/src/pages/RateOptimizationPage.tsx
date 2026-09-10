import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { Badge } from '../components/Badge';
import { AffiliateFilter } from '../components/AffiliateFilter';
import { rateApi } from '../api/client';
import { formatCurrency, formatNumber, formatPercent } from '../lib/format';
import { SERIES, tooltipStyle } from '../lib/theme';

export function RateOptimizationPage() {
  const [affiliate, setAffiliate] = useState('');
  const { data, isLoading, isError } = useQuery({
    queryKey: ['rate-optimization', affiliate],
    queryFn: () => rateApi.get(affiliate || undefined),
  });

  const pie = (data?.by_service ?? []).map((s) => ({ name: s.service, value: s.potential_savings }));

  return (
    <Layout
      title="Rate Optimization"
      subtitle="Reservations & savings plans — from FinOps hubs datasets"
      actions={<AffiliateFilter value={affiliate} onChange={setAffiliate} />}
    >
      {isLoading && <Spinner label="Loading recommendations…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Potential reservation savings"
              value={formatCurrency(data.potential_reservation_savings, data.currency, true)}
              sub="per month"
              accent="emerald"
            />
            <KpiCard
              label="Savings plan commitment"
              value={formatCurrency(data.savings_plan_commitment, data.currency, true)}
              accent="blue"
            />
            <KpiCard
              label="Savings to date"
              value={formatCurrency(data.savings_to_date, data.currency, true)}
              accent="emerald"
            />
            <KpiCard label="Active savings plans" value={formatNumber(data.active_savings_plans)} accent="blue" />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard title="Potential savings by service" subtitle="Reservation-eligible spend" className="lg:col-span-1">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                    {pie.map((_, i) => (
                      <Cell key={i} fill={SERIES[i % SERIES.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Reservation recommendations" subtitle="Ranked by monthly savings" className="lg:col-span-2">
              <div className="max-h-[300px] overflow-y-auto">
                <table className="min-w-full divide-y divide-slate-100">
                  <thead className="sticky top-0 bg-white">
                    <tr>
                      <th className="th">Affiliate</th>
                      <th className="th">Service</th>
                      <th className="th">Term</th>
                      <th className="th text-right">Qty</th>
                      <th className="th text-right">Savings</th>
                      <th className="th text-right">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {data.recommendations.map((rec, i) => (
                      <tr key={i} className="hover:bg-slate-50/60">
                        <td className="td font-mono text-xs text-slate-500">{rec.affiliate_id}</td>
                        <td className="td font-medium text-slate-900">{rec.service}</td>
                        <td className="td"><Badge tone="slate">{rec.term}</Badge></td>
                        <td className="td text-right">{rec.recommended_quantity}</td>
                        <td className="td text-right font-semibold text-emerald-600">
                          {formatCurrency(rec.monthly_savings)}
                        </td>
                        <td className="td text-right text-slate-500">{formatPercent(rec.savings_pct, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartCard>
          </div>
        </div>
      )}
    </Layout>
  );
}
