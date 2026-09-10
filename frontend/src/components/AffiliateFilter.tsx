import { useQuery } from '@tanstack/react-query';
import { FunnelIcon } from '@heroicons/react/20/solid';
import { affiliatesApi } from '../api/client';

interface AffiliateFilterProps {
  value: string; // '' = all
  onChange: (v: string) => void;
}

/** Shared "scope by affiliate" dropdown used across analytics pages. */
export function AffiliateFilter({ value, onChange }: AffiliateFilterProps) {
  const { data } = useQuery({ queryKey: ['affiliates'], queryFn: affiliatesApi.list });
  return (
    <div className="flex items-center gap-2">
      <FunnelIcon className="h-4 w-4 text-slate-400" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-slate-200 bg-white py-1.5 pl-2 pr-8 text-sm text-slate-700 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
      >
        <option value="">All affiliates</option>
        {data?.map((a) => (
          <option key={a.affiliate_id} value={a.affiliate_id}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
}
