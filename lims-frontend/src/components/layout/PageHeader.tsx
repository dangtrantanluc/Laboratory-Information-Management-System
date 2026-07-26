import type { ReactNode } from 'react';
import { Leaf } from 'lucide-react';

export function PageHeader({
  title,
  description,
  icon,
  actions,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-hairline bg-gradient-to-r from-blueberry/[0.07] via-berry/[0.04] to-transparent px-4 py-3.5 sm:px-5">
      {/* Hoạ tiết lá mờ (trang trí, không chắn tương tác) — đảo rất nhẹ như gió thoảng */}
      <Leaf
        aria-hidden
        strokeWidth={0.6}
        className="pointer-events-none absolute -right-6 -top-8 h-24 w-24 animate-sway text-blueberry/[0.07] sm:h-36 sm:w-36"
      />
      <Leaf
        aria-hidden
        strokeWidth={0.6}
        className="pointer-events-none absolute -bottom-10 right-24 hidden h-24 w-24 rotate-45 text-berry/[0.06] sm:block"
      />

      <div className="relative flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex animate-sprout items-center gap-3">
          {icon && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blueberry/10 text-blueberry ring-1 ring-blueberry/10 sm:h-10 sm:w-10">
              {icon}
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</h1>
            {description && (
              <p className="mt-0.5 line-clamp-2 text-xs text-subink sm:line-clamp-none sm:text-sm">
                {description}
              </p>
            )}
          </div>
        </div>
        {/* Dưới sm nút giãn đều chiều ngang; từ sm về hành vi ngang thông thường. */}
        {actions && (
          <div className="relative flex shrink-0 flex-wrap items-center gap-2 max-sm:w-full max-sm:[&>button]:flex-1">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
