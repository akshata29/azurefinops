import clsx from 'clsx';
import { ArrowDownRightIcon, ArrowUpRightIcon } from '@heroicons/react/20/solid';

interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  delta?: number; // percentage; positive = up
  deltaGoodWhenUp?: boolean;
  icon?: React.ReactNode;
  accent?: 'blue' | 'emerald' | 'amber' | 'red';
}

const accentBar: Record<NonNullable<KpiCardProps['accent']>, string> = {
  blue: 'bg-brand-600',
  emerald: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
};

export function KpiCard({
  label,
  value,
  sub,
  delta,
  deltaGoodWhenUp = true,
  icon,
  accent = 'blue',
}: KpiCardProps) {
  const up = (delta ?? 0) >= 0;
  const good = up === deltaGoodWhenUp;
  return (
    <div className="card relative overflow-hidden">
      <span className={clsx('absolute inset-y-0 left-0 w-1', accentBar[accent])} />
      <div className="card-pad">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-500">{label}</p>
          {icon && <span className="text-slate-300">{icon}</span>}
        </div>
        <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
        <div className="mt-1 flex items-center gap-2">
          {delta !== undefined && (
            <span
              className={clsx(
                'inline-flex items-center gap-0.5 text-xs font-semibold',
                good ? 'text-emerald-600' : 'text-red-600',
              )}
            >
              {up ? <ArrowUpRightIcon className="h-3.5 w-3.5" /> : <ArrowDownRightIcon className="h-3.5 w-3.5" />}
              {Math.abs(delta).toFixed(1)}%
            </span>
          )}
          {sub && <span className="text-xs text-slate-400">{sub}</span>}
        </div>
      </div>
    </div>
  );
}
