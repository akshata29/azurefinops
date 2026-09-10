import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MagnifyingGlassIcon, ChevronRightIcon } from '@heroicons/react/20/solid';
import { Layout } from '../components/Layout';
import { Spinner, ErrorState, EmptyState } from '../components/States';
import { Badge, StatusBadge } from '../components/Badge';
import { affiliatesApi } from '../api/client';
import { formatDate } from '../lib/format';

export function AffiliatesPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['affiliates'],
    queryFn: affiliatesApi.list,
  });
  const [q, setQ] = useState('');

  const rows = useMemo(() => {
    if (!data) return [];
    const term = q.trim().toLowerCase();
    if (!term) return data;
    return data.filter(
      (a) =>
        a.name.toLowerCase().includes(term) ||
        a.affiliate_id.toLowerCase().includes(term) ||
        a.billing_account.includes(term),
    );
  }, [data, q]);

  return (
    <Layout title="Affiliates" subtitle="Onboarded tenants — select one to drill into resource-level costs">
      {isLoading && <Spinner label="Loading affiliates…" />}
      {isError && <ErrorState />}
      {data && (
        <div className="card">
          <div className="flex items-center justify-between border-b border-slate-100 p-4">
            <div className="relative w-72">
              <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search name, id, billing account…"
                className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
              />
            </div>
            <span className="text-sm text-slate-400">{rows.length} of {data.length}</span>
          </div>
          {rows.length === 0 ? (
            <EmptyState message="No affiliates match your search." />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="th">Affiliate</th>
                    <th className="th">Agreement</th>
                    <th className="th">Billing account</th>
                    <th className="th">Status</th>
                    <th className="th">Onboarded</th>
                    <th className="th">Last refresh</th>
                    <th className="th"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {rows.map((a) => (
                    <tr key={a.affiliate_id} className="group cursor-pointer hover:bg-slate-50/60">
                      <td className="td">
                        <Link to={`/affiliates/${a.affiliate_id}`} className="block">
                          <div className="font-medium text-slate-900 group-hover:text-brand-700">{a.name}</div>
                          <div className="text-xs text-slate-400">{a.affiliate_id}</div>
                        </Link>
                      </td>
                      <td className="td">
                        <Badge tone={a.agreement_type === 'EA' ? 'blue' : 'slate'}>
                          {a.agreement_type}
                        </Badge>
                      </td>
                      <td className="td">
                        <span className="font-mono text-xs text-slate-600">{a.billing_account}</span>
                        {a.billing_profile && (
                          <span className="ml-1 font-mono text-xs text-slate-400">/ {a.billing_profile}</span>
                        )}
                      </td>
                      <td className="td"><StatusBadge status={a.status} /></td>
                      <td className="td">{formatDate(a.onboarded_on)}</td>
                      <td className="td">{formatDate(a.last_data_refresh)}</td>
                      <td className="td text-right">
                        <Link to={`/affiliates/${a.affiliate_id}`} className="inline-flex text-slate-300 group-hover:text-brand-600">
                          <ChevronRightIcon className="h-5 w-5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
