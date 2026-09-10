import { useState } from 'react';
import clsx from 'clsx';
import { ChevronRightIcon } from '@heroicons/react/20/solid';
import type { BreakdownNode } from '../api/types';
import { formatCurrency, formatPercent } from '../lib/format';

const LEVEL_LABEL = ['', 'Service category', 'Service', 'Resource type', 'Resource'];

const levelColor = ['', 'text-slate-900', 'text-brand-700', 'text-slate-600', 'text-slate-500'];

function Row({ node, depth, maxCost }: { node: BreakdownNode; depth: number; maxCost: number }) {
  const [open, setOpen] = useState(depth === 0);
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
          className={clsx(
            'h-4 w-4 shrink-0 text-slate-400 transition-transform',
            open && 'rotate-90',
            !hasChildren && 'invisible',
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className={clsx('truncate text-sm font-medium', levelColor[node.level])}>
            {node.name}
          </span>
          <span className="hidden text-[10px] uppercase tracking-wide text-slate-300 sm:inline">
            {LEVEL_LABEL[node.level]}
          </span>
        </div>
        <div className="hidden w-40 items-center gap-2 md:flex">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${barPct}%` }} />
          </div>
        </div>
        <span className="w-14 text-right text-xs text-slate-400">
          {formatPercent(node.pct_of_parent, 0)}
        </span>
        <span className="w-24 text-right text-sm font-semibold text-slate-900">
          {formatCurrency(node.cost, 'USD', true)}
        </span>
      </button>
      {open &&
        hasChildren &&
        node.children.map((c, i) => (
          <Row key={`${c.name}-${i}`} node={c} depth={depth + 1} maxCost={maxCost} />
        ))}
    </div>
  );
}

export function BreakdownTree({ nodes }: { nodes: BreakdownNode[] }) {
  const maxCost = Math.max(...nodes.map((n) => n.cost), 1);
  return (
    <div className="divide-y divide-slate-50">
      {nodes.map((n, i) => (
        <Row key={`${n.name}-${i}`} node={n} depth={0} maxCost={maxCost} />
      ))}
    </div>
  );
}
