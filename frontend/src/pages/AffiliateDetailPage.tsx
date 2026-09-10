import { useMemo, useState } from 'react';
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
import { ArrowLeftIcon, XMarkIcon } from '@heroicons/react/20/solid';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { ChartCard } from '../components/ChartCard';
import { Spinner, ErrorState } from '../components/States';
import { BreakdownTree } from '../components/BreakdownTree';
import { affiliatesApi, maccApi } from '../api/client';
import { formatCurrency, formatNumber } from '../lib/format';
import { SERIES, tooltipStyle } from '../lib/theme';
import {
  EMPTY_FILTERS,
  applyFilters,
  filterOptions,
  buildBreakdown,
  type ResourceFilters,
} from '../lib/breakdown';

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-2 pr-8 text-sm text-slate-700 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o || 'Other'}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AffiliateDetailPage() {
  const { id = '' } = useParams();
  const [filters, setFilters] = useState<ResourceFilters>(EMPTY_FILTERS);

  const resources = useQuery({
    queryKey: ['affiliate', id, 'resources'],
    queryFn: () => affiliatesApi.resources(id),
    enabled: !!id,
  });
  const affiliates = useQuery({ queryKey: ['affiliates'], queryFn: affiliatesApi.list });
  const macc = useQuery({
    queryKey: ['macc', 'detail', id],
    queryFn: () => maccApi.detail(id),
    enabled: !!id,
  });

  const all = resources.data ?? [];
  const affiliateName = affiliates.data?.find((a) => a.affiliate_id === id)?.name ?? id;
  const currency = all[0]?.currency ?? 'USD';

  const options = useMemo(() => filterOptions(all, filters), [all, filters]);
  const filtered = useMemo(() => applyFilters(all, filters), [all, filters]);
  const breakdown = useMemo(() => buildBreakdown(filtered), [filtered]);
  const total = useMemo(() => filtered.reduce((s, r) => s + r.cost, 0), [filtered]);
  const categoryCount = useMemo(
    () => new Set(filtered.map((r) => r.service_category)).size,
    [filtered],
  );
  const categoryData = useMemo(
    () => breakdown.map((c) => ({ name: c.name, value: c.cost })),
    [breakdown],
  );
  const topResources = useMemo(
    () => [...filtered].sort((a, b) => b.cost - a.cost).slice(0, 10),
    [filtered],
  );

  const hasFilters = Object.values(filters).some(Boolean);

  // Cascading: changing a parent resets its descendants.
  const update = (patch: Partial<ResourceFilters>) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <Layout
      title={affiliateName}
      subtitle="Resource-level cost drill-down · ServiceCategory → Service → ResourceType → Resource"
    >
      <Link
        to="/affiliates"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"
      >
        <ArrowLeftIcon className="h-4 w-4" /> Back to affiliates
      </Link>

      {(resources.isLoading || macc.isLoading) && <Spinner label="Loading affiliate detail…" />}
      {resources.isError && <ErrorState />}

      {resources.data && (
        <div className="space-y-6">
          {/* Filters */}
          <div className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">Filters</h3>
              {hasFilters && (
                <button
                  onClick={() => setFilters(EMPTY_FILTERS)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                >
                  <XMarkIcon className="h-3.5 w-3.5" /> Clear
                </button>
              )}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <FilterSelect
                label="Service category"
                value={filters.service_category}
                options={options.categories}
                onChange={(v) =>
                  update({ service_category: v, service: '', resource_type: '', resource: '' })
                }
              />
              <FilterSelect
                label="Service"
                value={filters.service}
                options={options.services}
                onChange={(v) => update({ service: v, resource_type: '', resource: '' })}
              />
              <FilterSelect
                label="Resource type"
                value={filters.resource_type}
                options={options.resource_types}
                onChange={(v) => update({ resource_type: v, resource: '' })}
              />
              <FilterSelect
                label="Resource"
                value={filters.resource}
                options={options.resources}
                onChange={(v) => update({ resource: v })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total resource cost"
              value={formatCurrency(total, currency, true)}
              sub={hasFilters ? 'filtered' : undefined}
              accent="blue"
            />
            <KpiCard label="Resources" value={formatNumber(filtered.length)} accent="emerald" />
            <KpiCard label="Service categories" value={formatNumber(categoryCount)} accent="blue" />
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
                {breakdown.length ? (
                  <BreakdownTree nodes={breakdown} />
                ) : (
                  <p className="py-8 text-center text-sm text-slate-400">No resources match the filters.</p>
                )}
              </div>
            </ChartCard>

            <ChartCard title="By service category" subtitle="Share of filtered cost">
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
                  {topResources.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50/60">
                      <td className="td font-medium text-slate-900">{r.resource_name}</td>
                      <td className="td font-mono text-xs text-slate-500">{r.resource_group}</td>
                      <td className="td">{r.service_name}</td>
                      <td className="td text-slate-500">{r.resource_type}</td>
                      <td className="td font-mono text-xs text-slate-500">{r.region || '—'}</td>
                      <td className="td text-right font-semibold text-slate-900">{formatCurrency(r.cost)}</td>
                    </tr>
                  ))}
                  {!topResources.length && (
                    <tr>
                      <td className="td text-center text-slate-400" colSpan={6}>
                        No resources match the filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
