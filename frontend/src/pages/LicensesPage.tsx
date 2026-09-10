import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Layout } from '../components/Layout';
import { KpiCard } from '../components/KpiCard';
import { Spinner, ErrorState } from '../components/States';
import { ProgressBar } from '../components/ProgressBar';
import { AffiliateFilter } from '../components/AffiliateFilter';
import { licensesApi } from '../api/client';
import { formatCurrency, formatDate, formatNumber, formatPercent } from '../lib/format';

export function LicensesPage() {
  const [affiliate, setAffiliate] = useState('');
  const { data, isLoading, isError } = useQuery({
    queryKey: ['licenses', affiliate],
    queryFn: () => licensesApi.list(affiliate || undefined),
  });

  const totals = useMemo(() => {
    if (!data) return { assigned: 0, consumed: 0, annualCost: 0 };
    return data.reduce(
      (acc, l) => ({
        assigned: acc.assigned + l.assigned,
        consumed: acc.consumed + l.consumed,
        annualCost: acc.annualCost + l.assigned * l.unit_cost * 12,
      }),
      { assigned: 0, consumed: 0, annualCost: 0 },
    );
  }, [data]);

  const utilization = totals.assigned ? (totals.consumed / totals.assigned) * 100 : 0;

  return (
    <Layout
      title="Licenses"
      subtitle="Imported license inventory joined to affiliates"
      actions={<AffiliateFilter value={affiliate} onChange={setAffiliate} />}
    >
      {isLoading && <Spinner label="Loading licenses…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCard label="Assigned seats" value={formatNumber(totals.assigned)} accent="blue" />
            <KpiCard
              label="Utilization"
              value={formatPercent(utilization)}
              sub={`${formatNumber(totals.consumed)} in use`}
              accent={utilization > 85 ? 'emerald' : 'amber'}
            />
            <KpiCard
              label="Est. annual cost"
              value={formatCurrency(totals.annualCost, 'USD', true)}
              accent="emerald"
            />
          </div>

          <div className="card">
            <div className="border-b border-slate-100 p-4">
              <h3 className="text-sm font-semibold text-slate-900">License inventory</h3>
              <p className="text-xs text-slate-400">Phase-2 import — placeholder join key = affiliate_id</p>
            </div>
            <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
              <table className="min-w-full divide-y divide-slate-100">
                <thead className="sticky top-0 z-10 bg-slate-50">
                  <tr>
                    <th className="th">Affiliate</th>
                    <th className="th">Product</th>
                    <th className="th">SKU</th>
                    <th className="th">Utilization</th>
                    <th className="th text-right">Assigned</th>
                    <th className="th text-right">Unit / mo</th>
                    <th className="th">Renewal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {data.map((l, i) => {
                    const util = l.assigned ? (l.consumed / l.assigned) * 100 : 0;
                    return (
                      <tr key={`${l.affiliate_id}-${l.sku}-${i}`} className="hover:bg-slate-50/60">
                        <td className="td font-mono text-xs text-slate-500">{l.affiliate_id}</td>
                        <td className="td font-medium text-slate-900">{l.product}</td>
                        <td className="td font-mono text-xs text-slate-500">{l.sku}</td>
                        <td className="td w-48">
                          <div className="flex items-center gap-2">
                            <ProgressBar value={util} tone={util > 90 ? 'emerald' : util > 70 ? 'blue' : 'amber'} />
                            <span className="w-10 text-right text-xs text-slate-500">{formatPercent(util, 0)}</span>
                          </div>
                        </td>
                        <td className="td text-right">{formatNumber(l.assigned)}</td>
                        <td className="td text-right">{formatCurrency(l.unit_cost)}</td>
                        <td className="td">{formatDate(l.renewal_date)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
