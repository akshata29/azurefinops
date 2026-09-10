import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Layout } from '../components/Layout';
import { Spinner, ErrorState } from '../components/States';
import { HierarchyTree } from '../components/HierarchyTree';
import { ChartCard } from '../components/ChartCard';
import { affiliatesApi } from '../api/client';
import { formatCurrency } from '../lib/format';

export function HierarchyPage() {
  const affiliates = useQuery({ queryKey: ['affiliates'], queryFn: affiliatesApi.list });
  const [selected, setSelected] = useState<string | null>(null);
  const activeId = selected ?? affiliates.data?.[0]?.affiliate_id ?? null;

  const hierarchy = useQuery({
    queryKey: ['hierarchy', activeId],
    queryFn: () => affiliatesApi.hierarchy(activeId as string),
    enabled: !!activeId,
  });

  return (
    <Layout
      title="Billing Hierarchy"
      subtitle="Billing profile → invoice section → subscription → resource group → resource"
    >
      {affiliates.isLoading && <Spinner label="Loading…" />}
      {affiliates.isError && <ErrorState />}
      {affiliates.data && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[300px_1fr]">
          <div className="card overflow-hidden">
            <div className="border-b border-slate-100 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Customer hierarchy</h3>
              <p className="text-xs text-slate-400">Select an affiliate</p>
            </div>
            <div className="max-h-[70vh] divide-y divide-slate-50 overflow-y-auto">
              {affiliates.data.map((a) => (
                <button
                  key={a.affiliate_id}
                  onClick={() => setSelected(a.affiliate_id)}
                  className={`flex w-full items-center justify-between px-4 py-3 text-left text-sm transition-colors ${
                    a.affiliate_id === activeId ? 'bg-brand-50 font-medium text-brand-700' : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <span className="truncate">{a.name}</span>
                  <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{a.agreement_type}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            {hierarchy.isLoading && <Spinner label="Loading hierarchy…" />}
            {hierarchy.isError && <ErrorState />}
            {hierarchy.data && (
              <ChartCard
                title={hierarchy.data.affiliate_name}
                subtitle={`Total ${formatCurrency(hierarchy.data.total_cost, hierarchy.data.currency)} · expand to drill to resource`}
              >
                <div className="mb-2 flex items-center justify-end gap-6 pr-3 text-[10px] uppercase tracking-wide text-slate-400">
                  <span className="hidden md:inline w-32 text-right">Share</span>
                  <span className="w-12 text-right">% parent</span>
                  <span className="w-24 text-right">Cost</span>
                </div>
                <div className="max-h-[calc(100vh-260px)] overflow-y-auto">
                  <HierarchyTree root={hierarchy.data.root} />
                </div>
              </ChartCard>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
