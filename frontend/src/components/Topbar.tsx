import { useQuery } from '@tanstack/react-query';
import { SunIcon, MoonIcon } from '@heroicons/react/24/outline';
import { summaryApi } from '../api/client';
import { formatDate } from '../lib/format';
import { useTheme } from '../lib/useTheme';

interface TopbarProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function Topbar({ title, subtitle, actions }: TopbarProps) {
  const { data } = useQuery({ queryKey: ['summary'], queryFn: summaryApi.get });
  const { theme, toggle } = useTheme();
  const refreshed = data ? formatDate(data.generated_at) : '—';
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-4">
        {actions}
        <button
          onClick={toggle}
          aria-label="Toggle theme"
          title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
        >
          {theme === 'dark' ? <SunIcon className="h-5 w-5" /> : <MoonIcon className="h-5 w-5" />}
        </button>
        <div className="text-right">
          <p className="text-xs text-slate-400">Last refreshed</p>
          <p className="text-sm font-medium text-slate-700">{refreshed}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
          FO
        </div>
      </div>
    </header>
  );
}
