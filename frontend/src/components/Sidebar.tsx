import { NavLink } from 'react-router-dom';
import clsx from 'clsx';
import {
  Squares2X2Icon,
  BuildingOffice2Icon,
  BanknotesIcon,
  ChartBarIcon,
  KeyIcon,
  ReceiptPercentIcon,
  CpuChipIcon,
  RectangleGroupIcon,
  ScaleIcon,
} from '@heroicons/react/24/outline';

const nav = [
  { to: '/', label: 'Overview', icon: Squares2X2Icon, end: true },
  { to: '/affiliates', label: 'Affiliates', icon: BuildingOffice2Icon },
  { to: '/hierarchy', label: 'Billing Hierarchy', icon: RectangleGroupIcon },
  { to: '/macc', label: 'MACC Commitment', icon: BanknotesIcon },
  { to: '/costs', label: 'Cost & Usage', icon: ChartBarIcon },
  { to: '/tco', label: 'Total Cost (TCO)', icon: ScaleIcon },
  { to: '/rate-optimization', label: 'Rate Optimization', icon: ReceiptPercentIcon },
  { to: '/ai', label: 'AI & Copilot', icon: CpuChipIcon },
  { to: '/licenses', label: 'Licenses', icon: KeyIcon },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-slate-200 bg-white px-4 py-5">
      <div className="mb-8 flex items-center gap-3 px-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
          <ChartBarIcon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">Affiliate FinOps</p>
          <p className="text-[11px] text-slate-400">Cost &amp; MACC control center</p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => clsx('nav-link', isActive && 'nav-link-active')}
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-500">
        Powered by <span className="font-medium text-slate-700">FinOps hubs</span> + MACC add-on.
        Data via FOCUS exports &amp; Consumption REST.
      </div>
    </aside>
  );
}
