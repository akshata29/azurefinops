import clsx from 'clsx';
import type { OnboardingStatus, MaccStatus } from '../api/types';

type Tone = 'green' | 'amber' | 'red' | 'blue' | 'slate';

const toneClasses: Record<Tone, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  red: 'bg-red-50 text-red-700 ring-red-600/20',
  blue: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  slate: 'bg-slate-100 text-slate-600 ring-slate-500/20',
};

export function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        toneClasses[tone],
      )}
    >
      {children}
    </span>
  );
}

const statusTone: Record<OnboardingStatus, Tone> = {
  Active: 'green',
  Onboarding: 'blue',
  Error: 'red',
  Paused: 'slate',
};

export function StatusBadge({ status }: { status: OnboardingStatus }) {
  return <Badge tone={statusTone[status]}>{status}</Badge>;
}

export function MaccStatusBadge({ status }: { status: MaccStatus }) {
  const tone: Tone = status === 'Active' ? 'green' : status === 'Expired' ? 'red' : 'slate';
  return <Badge tone={tone}>{status}</Badge>;
}

export function TrackBadge({ onTrack }: { onTrack: boolean }) {
  return <Badge tone={onTrack ? 'green' : 'amber'}>{onTrack ? 'On track' : 'At risk'}</Badge>;
}
