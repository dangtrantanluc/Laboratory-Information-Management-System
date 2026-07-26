import { useEffect, useRef, useState, type ReactNode } from 'react';
import { MoreHorizontal } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface OverflowItem {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  tone?: 'default' | 'danger';
}

/**
 * Nút "⋯" gom các hành động phụ — dùng ở PageHeader dưới sm, nơi 3 nút ngang
 * sẽ tràn hoặc bị nén trên màn 360px.
 */
export function OverflowMenu({
  items,
  className,
  label = 'Hành động khác',
}: {
  items: OverflowItem[];
  className?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) =>
      ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onEsc);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div className={cn('relative', className)} ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex h-11 w-11 items-center justify-center rounded-lg border border-hairline bg-surface text-stem transition-colors hover:bg-plate hover:text-ink sm:h-10 sm:w-10"
      >
        <MoreHorizontal size={18} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 animate-scale-in rounded-xl border border-hairline bg-surface p-1.5 shadow-pop"
        >
          {items.map((it) => (
            <button
              key={it.label}
              role="menuitem"
              onClick={() => {
                setOpen(false);
                it.onClick();
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-lg px-2.5 py-2.5 text-sm font-medium transition-colors',
                it.tone === 'danger'
                  ? 'text-overdue hover:bg-overdue/10'
                  : 'text-stem hover:bg-blueberry/10 hover:text-blueberry',
              )}
            >
              {it.icon}
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
