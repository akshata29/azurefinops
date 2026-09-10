import clsx from 'clsx';

interface ProgressProps {
  value: number; // 0-100
  tone?: 'blue' | 'emerald' | 'amber' | 'red';
}

const toneClasses: Record<NonNullable<ProgressProps['tone']>, string> = {
  blue: 'bg-brand-600',
  emerald: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
};

export function ProgressBar({ value, tone = 'blue' }: ProgressProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={clsx('h-full rounded-full', toneClasses[tone])} style={{ width: `${pct}%` }} />
    </div>
  );
}
