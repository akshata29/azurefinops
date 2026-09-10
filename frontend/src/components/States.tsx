import clsx from 'clsx';

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-400">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function ErrorState({ message }: { message?: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      Failed to load data. {message ?? 'Is the backend running on :8000?'}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className={clsx('rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400')}>
      {message}
    </div>
  );
}
