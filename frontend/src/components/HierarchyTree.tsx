import { useState } from 'react';
import clsx from 'clsx';
import { ChevronRightIcon } from '@heroicons/react/20/solid';
import type { HierarchyNode } from '../api/types';
import { formatCurrency, formatPercent } from '../lib/format';

const TYPE_LABEL: Record<string, string> = {
  billingProfile: 'Billing profile',
  invoiceSection: 'Invoice section',
  subscription: 'Subscription',
  resourceGroup: 'Resource group',
  resource: 'Resource',
};

const typeTone: Record<string, string> = {
  billingProfile: 'text-slate-900',
  invoiceSection: 'text-brand-700',
  subscription: 'text-slate-700',
  resourceGroup: 'text-slate-600',
  resource: 'text-slate-500',
};

function Row({ node, depth, maxCost }: { node: HierarchyNode; depth: number; maxCost: number }) {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;
  const barPct = maxCost ? (node.cost / maxCost) * 100 : 0;

  return (
    <div>
      <button
        onClick={() => hasChildren && setOpen((v) => !v)}
        className={clsx(
          'group flex w-full items-center gap-2 rounded-lg py-2 pr-3 text-left transition-colors',
          hasChildren ? 'hover:bg-slate-50' : 'cursor-default',
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        <ChevronRightIcon
          className={clsx('h-4 w-4 shrink-0 text-slate-400 transition-transform', open && 'rotate-90', !hasChildren && 'invisible')}
        />
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className={clsx('truncate text-sm font-medium', typeTone[node.node_type])}>{node.name}</span>
          <span className="hidden shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400 sm:inline">
            {TYPE_LABEL[node.node_type] ?? node.node_type}
          </span>
          {node.identifier && (
            <span className="hidden truncate font-mono text-[11px] text-slate-400 md:inline">{node.identifier}</span>
          )}
        </div>
        <div className="hidden w-32 items-center md:flex">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${barPct}%` }} />
          </div>
        </div>
        <span className="w-12 text-right text-xs text-slate-400">{formatPercent(node.pct_of_parent, 0)}</span>
        <span className="w-24 text-right text-sm font-semibold text-slate-900">{formatCurrency(node.cost, 'USD', true)}</span>
      </button>
      {open && hasChildren && node.children.map((c, i) => <Row key={`${c.name}-${i}`} node={c} depth={depth + 1} maxCost={maxCost} />)}
    </div>
  );
}

export function HierarchyTree({ root }: { root: HierarchyNode }) {
  return (
    <div className="divide-y divide-slate-50">
      <Row node={root} depth={0} maxCost={root.cost || 1} />
    </div>
  );
}
