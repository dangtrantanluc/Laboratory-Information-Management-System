import type { ReactNode } from 'react';
import { Sprout, Loader2 } from 'lucide-react';
import { cn } from '@/lib/cn';

export function EmptyState({
  icon,
  title = 'Không có dữ liệu',
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 py-14 text-center',
        className,
      )}
    >
      {/* Empty state botanical: mầm cây trên nền lá — ấm hơn "hộp trống" */}
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blueberry/10 text-blueberry">
        {icon ?? <Sprout size={24} />}
      </div>
      <div>
        <p className="text-sm font-semibold text-ink">{title}</p>
        {description && <p className="mt-1 text-sm text-subink">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('animate-spin text-stem', className)} />;
}

export function LoadingState({ label = 'Đang tải dữ liệu…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14 text-subink">
      <Spinner className="h-6 w-6" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

/** Skeleton cho DataTable ở chế độ thẻ (dưới md). */
export function CardSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-hairline">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex flex-col gap-2 px-4 py-3.5">
          <div className="h-4 w-2/3 animate-pulse rounded bg-hairline/70" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-hairline/50" />
          <div className="h-3 w-2/5 animate-pulse rounded bg-hairline/50" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton rows cho bảng khi loading. */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y divide-hairline">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3.5">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="h-3.5 animate-pulse rounded bg-hairline/70"
              style={{ width: `${[28, 20, 16, 24, 18][c % 5]}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
