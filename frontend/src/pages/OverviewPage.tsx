import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  PieChart,
  Pie,
  Legend,
} from 'recharts';
import {
  BuildingOffice2Icon,
  BanknotesIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { ProgressBar } from '../components/ProgressBar';
import { TrackBadge } from '../components/Badge';
import { summaryApi, maccApi, costsApi, billingApi } from '../api/client';
import { formatCurrency, formatMonth, formatPercent, formatNumber } from '../lib/format';
import { SERIES, tooltipStyle } from '../lib/theme';

export function OverviewPage() {
  const summary = useQuery({ queryKey: ['summary'], queryFn: summaryApi.get });
  const balances = useQuery({ queryKey: ['macc', 'balances'], queryFn: maccApi.balances });
  const costs = useQuery({ queryKey: ['costs', 'all'], queryFn: () => costsApi.summary() });
  const prepayment = useQuery({ queryKey: ['prepayment'], queryFn: billingApi.prepayment });
  const offerMix = useQuery({ queryKey: ['offer-mix'], queryFn: billingApi.offerMix });

  const loading = summary.isLoading || balances.isLoading || costs.isLoading;
  const error = summary.isError || balances.isError || costs.isError;

  return (
    <Layout title="Portfolio Overview" subtitle="All affiliates · Azure cost & MACC consumption">
      {loading && <Spinner label="Loading portfolio…" />}
      {error && <ErrorState />}
      {summary.data && balances.data && costs.data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Affiliates"
              value={formatNumber(summary.data.affiliate_count)}
              sub={`${summary.data.active_count} active`}
              icon={<BuildingOffice2Icon className="h-5 w-5" />}
              accent="blue"
            />
            <KpiCard
              label="Total MACC Commitment"
              value={formatCurrency(summary.data.total_commitment, summary.data.currency, true)}
              sub={`${formatPercent(summary.data.percent_consumed)} consumed`}
              icon={<BanknotesIcon className="h-5 w-5" />}
              accent="emerald"
            />
            <KpiCard
              label="Remaining Balance"
              value={formatCurrency(summary.data.total_remaining, summary.data.currency, true)}
              sub={`${formatCurrency(summary.data.total_consumed, summary.data.currency, true)} drawn down`}
              icon={<ChartBarIcon className="h-5 w-5" />}
              accent="blue"
            />
            <KpiCard
              label="Affiliates At Risk"
              value={formatNumber(summary.data.at_risk_count)}
              sub="off-track vs. commitment pace"
              icon={<ExclamationTriangleIcon className="h-5 w-5" />}
              accent={summary.data.at_risk_count > 0 ? 'amber' : 'emerald'}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <ChartCard
              title="Cost trend"
              subtitle="Aggregated monthly Azure cost across all affiliates"
              className="lg:col-span-2"
            >
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={costs.data.trend} margin={{ left: 4, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                  <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip
                    formatter={(v: number) => formatCurrency(v)}
                    labelFormatter={formatMonth}
                    contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }}
                  />
                  <Area type="monotone" dataKey="cost" stroke="#2563eb" strokeWidth={2} fill="url(#costFill)" name="Cost" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Portfolio commitment" subtitle="Consumed vs. remaining">
              <div className="flex h-[280px] flex-col justify-center gap-6">
                <div>
                  <div className="mb-2 flex items-baseline justify-between">
                    <span className="text-sm text-slate-500">Consumed</span>
                    <span className="text-lg font-semibold text-slate-900">
                      {formatPercent(summary.data.percent_consumed)}
                    </span>
                  </div>
                  <ProgressBar value={summary.data.percent_consumed} tone="emerald" />
                </div>
                <dl className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <dt className="text-xs text-slate-400">Consumed</dt>
                    <dd className="mt-1 text-base font-semibold text-slate-900">
                      {formatCurrency(summary.data.total_consumed, summary.data.currency, true)}
                    </dd>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <dt className="text-xs text-slate-400">Remaining</dt>
                    <dd className="mt-1 text-base font-semibold text-slate-900">
                      {formatCurrency(summary.data.total_remaining, summary.data.currency, true)}
                    </dd>
                  </div>
                </dl>
                <div className="rounded-lg bg-brand-50 p-3 text-xs text-brand-700">
                  MTD cost {formatCurrency(costs.data.total_cost_mtd, 'USD', true)} ·
                  {' '}
                  {costs.data.mom_change_pct >= 0 ? '▲' : '▼'} {formatPercent(Math.abs(costs.data.mom_change_pct))} MoM
                </div>
              </div>
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="Top affiliates by consumption" subtitle="% of MACC commitment consumed">
              <div className="space-y-3">
                {[...balances.data]
                  .sort((a, b) => b.percent_consumed - a.percent_consumed)
                  .slice(0, 6)
                  .map((b) => (
                    <div key={b.affiliate_id}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium text-slate-700">{b.affiliate_name}</span>
                        <span className="flex items-center gap-2 text-slate-500">
                          {formatPercent(b.percent_consumed)}
                          <TrackBadge onTrack={b.on_track} />
                        </span>
                      </div>
                      <ProgressBar
                        value={b.percent_consumed}
                        tone={b.on_track ? 'blue' : 'amber'}
                      />
                    </div>
                  ))}
              </div>
            </ChartCard>

            <ChartCard title="Cost by service" subtitle="Aggregated across affiliates">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={costs.data.by_service.slice(0, 8)}
                  layout="vertical"
                  margin={{ left: 8, right: 16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => formatCurrency(v, 'USD', true)} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="service" width={120} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                    {costs.data.by_service.slice(0, 8).map((_, i) => (
                      <Cell key={i} fill={i === 0 ? '#1d4ed8' : '#60a5fa'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {prepayment.data && offerMix.data && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <ChartCard title="MACC & Azure prepayment" subtitle="Portfolio balance vs. utilized">
                <div className="flex h-[260px] flex-col justify-center gap-5">
                  <div>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="text-slate-500">MACC total balance</span>
                      <span className="font-semibold text-slate-900">
                        {formatCurrency(prepayment.data.macc_total_balance, prepayment.data.currency, true)}
                      </span>
                    </div>
                    <ProgressBar
                      value={(prepayment.data.macc_utilized / prepayment.data.macc_total_balance) * 100}
                      tone="blue"
                    />
                    <p className="mt-1 text-xs text-slate-400">
                      {formatCurrency(prepayment.data.macc_utilized, prepayment.data.currency, true)} utilized
                    </p>
                  </div>
                  <dl className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <dt className="text-xs text-slate-400">Commit to consume</dt>
                      <dd className="mt-1 text-sm font-semibold text-slate-900">
                        {formatCurrency(prepayment.data.commit_to_consume, prepayment.data.currency, true)}
                      </dd>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3">
                      <dt className="text-xs text-slate-400">Azure prepayment</dt>
                      <dd className="mt-1 text-sm font-semibold text-slate-900">
                        {formatCurrency(prepayment.data.azure_prepayment, prepayment.data.currency, true)}
                      </dd>
                    </div>
                  </dl>
                </div>
              </ChartCard>

              <ChartCard title="Invoiced usage by offer type" subtitle="Annualized, by pricing model">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={offerMix.data.map((o) => ({ name: o.name, value: o.invoiced_usage }))}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={95}
                      paddingAngle={2}
                    >
                      {offerMix.data.map((_, i) => (
                        <Cell key={i} fill={SERIES[i % SERIES.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
