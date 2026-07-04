import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/** Danh sách mô tả read-only (label + value) dùng cho modal xem chi tiết. */
export function DescList({ children, className }: { children: ReactNode; className?: string }) {
  return <dl className={cn('grid grid-cols-1 gap-x-6 gap-y-3.5 sm:grid-cols-2', className)}>{children}</dl>;
}

export function DescItem({
  label,
  value,
  full,
}: {
  label: ReactNode;
  value: ReactNode;
  /** Chiếm trọn 2 cột (dùng cho nội dung dài). */
  full?: boolean;
}) {
  const empty = value === null || value === undefined || value === '';
  return (
    <div className={full ? 'sm:col-span-2' : undefined}>
      <dt className="text-xs font-semibold uppercase tracking-wide text-stem">{label}</dt>
      <dd className={cn('mt-1 text-sm', empty ? 'text-subink' : 'text-ink')}>{empty ? '—' : value}</dd>
    </div>
  );
}
