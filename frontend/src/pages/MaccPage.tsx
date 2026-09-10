import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import { Layout } from '../components/Layout';
import { ChartCard } from '../components/ChartCard';
import { KpiCard } from '../components/KpiCard';
import { Spinner, ErrorState } from '../components/States';
import { ProgressBar } from '../components/ProgressBar';
import { TrackBadge } from '../components/Badge';
import { maccApi } from '../api/client';
import { formatCurrency, formatDate, formatMonth, formatPercent } from '../lib/format';

export function MaccPage() {
  const balances = useQuery({ queryKey: ['macc', 'balances'], queryFn: maccApi.balances });
  const [selected, setSelected] = useState<string | null>(null);
  const activeId = selected ?? balances.data?.[0]?.affiliate_id ?? null;

  const detail = useQuery({
    queryKey: ['macc', 'detail', activeId],
    queryFn: () => maccApi.detail(activeId as string),
    enabled: !!activeId,
  });

  return (
    <Layout title="MACC Commitment" subtitle="Remaining balance, burn-down & projected exhaustion">
      {balances.isLoading && <Spinner label="Loading commitments…" />}
      {balances.isError && <ErrorState />}
      {balances.data && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[380px_1fr]">
          {/* Master list */}
          <div className="card overflow-hidden">
            <div className="border-b border-slate-100 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Affiliates</h3>
              <p className="text-xs text-slate-400">Sorted by % consumed</p>
            </div>
            <div className="max-h-[70vh] divide-y divide-slate-50 overflow-y-auto">
              {[...balances.data]
                .sort((a, b) => b.percent_consumed - a.percent_consumed)
                .map((b) => {
                  const isActive = b.affiliate_id === activeId;
                  return (
                    <button
                      key={b.affiliate_id}
                      onClick={() => setSelected(b.affiliate_id)}
                      className={`w-full px-4 py-3 text-left transition-colors ${
                        isActive ? 'bg-brand-50' : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-900">{b.affiliate_name}</span>
                        <TrackBadge onTrack={b.on_track} />
                      </div>
                      <div className="mb-1.5 flex items-center justify-between text-xs text-slate-500">
                        <span>{formatCurrency(b.remaining_balance, b.currency, true)} left</span>
                        <span>{formatPercent(b.percent_consumed)}</span>
                      </div>
                      <ProgressBar value={b.percent_consumed} tone={b.on_track ? 'blue' : 'amber'} />
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Detail */}
          <div className="space-y-6">
            {detail.isLoading && <Spinner label="Loading burn-down…" />}
            {detail.isError && <ErrorState />}
            {detail.data && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                  <KpiCard
                    label="Commitment"
                    value={formatCurrency(detail.data.balance.commitment_amount, detail.data.balance.currency, true)}
                    accent="blue"
                  />
                  <KpiCard
                    label="Remaining"
                    value={formatCurrency(detail.data.balance.remaining_balance, detail.data.balance.currency, true)}
                    sub={`${formatPercent(detail.data.balance.percent_consumed)} consumed`}
                    accent="emerald"
                  />
                  <KpiCard
                    label="Days remaining"
                    value={detail.data.balance.days_remaining.toLocaleString()}
                    sub={`ends ${formatDate(detail.data.balance.end_date)}`}
                    accent="blue"
                  />
                  <KpiCard
                    label="Projected exhaustion"
                    value={
                      detail.data.balance.projected_exhaustion_date
                        ? formatDate(detail.data.balance.projected_exhaustion_date)
                        : 'After term'
                    }
                    sub={detail.data.balance.on_track ? 'on track' : 'off pace'}
                    accent={detail.data.balance.on_track ? 'emerald' : 'amber'}
                  />
                </div>

                <ChartCard
                  title={`Burn-down — ${detail.data.balance.affiliate_name}`}
                  subtitle="Remaining commitment vs. cumulative consumption (last 12 months)"
                >
                  <ResponsiveContainer width="100%" height={320}>
                    <ComposedChart data={detail.data.trend} margin={{ left: 4, right: 8, top: 8 }}>
                      <defs>
                        <linearGradient id="remainFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2563eb" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                      <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={64} />
                      <Tooltip formatter={(v: number) => formatCurrency(v)} labelFormatter={formatMonth} contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                      <Area type="monotone" dataKey="remaining_balance" name="Remaining" stroke="#2563eb" strokeWidth={2} fill="url(#remainFill)" />
                      <Line type="monotone" dataKey="consumed_cumulative" name="Consumed (cumulative)" stroke="#10b981" strokeWidth={2} dot={false} />
                      <ReferenceLine y={0} stroke="#cbd5e1" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </ChartCard>

                <div className="card">
                  <div className="border-b border-slate-100 p-4">
                    <h3 className="text-sm font-semibold text-slate-900">Drawdown events</h3>
                    <p className="text-xs text-slate-400">Invoiced consumption decrementing the commitment</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-100">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="th">Date</th>
                          <th className="th">Description</th>
                          <th className="th text-right">Charges</th>
                          <th className="th text-right">Remaining after</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {detail.data.events.map((e, i) => (
                          <tr key={i} className="hover:bg-slate-50/60">
                            <td className="td">{formatDate(e.event_date)}</td>
                            <td className="td">{e.description}</td>
                            <td className="td text-right font-medium text-slate-900">{formatCurrency(e.charges)}</td>
                            <td className="td text-right text-slate-500">{formatCurrency(e.remaining_after)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
