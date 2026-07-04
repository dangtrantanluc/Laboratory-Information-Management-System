import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type BadgeTone =
  | 'success'
  | 'pending'
  | 'warning'
  | 'overdue'
  | 'muted'
  | 'info'
  | 'neutral';

const TONES: Record<BadgeTone, string> = {
  success: 'bg-success/10 text-success ring-success/20',
  pending: 'bg-pending/10 text-pending ring-pending/20',
  warning: 'bg-warning/10 text-[#b45309] ring-warning/20',
  overdue: 'bg-overdue/10 text-overdue ring-overdue/20',
  info: 'bg-berry/10 text-berry ring-berry/20',
  muted: 'bg-stem/10 text-stem ring-stem/20',
  neutral: 'bg-plate text-subink ring-hairline',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
  dot,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
