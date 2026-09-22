import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { MoreHorizontal } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface OverflowItem {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  tone?: 'default' | 'danger';
}

/**
 * Nút "⋯" gom các hành động phụ.
 *
 * Dùng ở PageHeader dưới sm (3 nút ngang sẽ tràn trên màn 360px) VÀ ở cột hành động
 * của DataTable, nơi nó thay cho một dãy icon nhỏ sát nhau.
 *
 * MENU VẼ QUA PORTAL, KHÔNG PHẢI `absolute`. Lý do: DataTable bọc bảng trong
 * `overflow-x-auto` (DataTable.tsx) — theo CSS, đặt overflow-x thì overflow-y ngầm
 * thành `auto` chứ không còn `visible`, nên menu con định vị tuyệt đối sẽ bị CẮT
 * ngay mép dưới hàng. Portal + `position: fixed` thoát khỏi mọi khung cắt.
 *
 * Menu đóng khi cuộn: toạ độ đã chốt lúc mở, cuộn tiếp sẽ làm nó trôi khỏi nút.
 */
export function OverflowMenu({
  items,
  className,
  label = 'Hành động khác',
  compact = false,
}: {
  items: OverflowItem[];
  className?: string;
  label?: string;
  /** Nút nhỏ, nền trong suốt — hợp với cột hành động trong bảng. */
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    // `capture` để bắt cả cuộn bên trong khung overflow của bảng, không chỉ cuộn trang.
    const onScroll = () => setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onEsc);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onEsc);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
    };
  }, []);

  // Đo sau khi DOM cập nhật nhưng TRƯỚC khi trình duyệt vẽ, để menu không nhấp nháy
  // ở góc trên-trái một khung hình rồi mới nhảy về đúng chỗ.
  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    setPos({ top: r.bottom + 6, right: window.innerWidth - r.right });
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div className={cn('relative', className)} ref={ref}>
      <button
        ref={btnRef}
        onClick={() => setOpen((o) => !o)}
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="menu"
        className={cn(
          'flex items-center justify-center rounded-lg text-stem transition-colors hover:bg-plate hover:text-ink',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blueberry/40',
          compact
            ? 'h-10 w-10 sm:h-9 sm:w-9'
            : 'h-11 w-11 border border-hairline bg-surface sm:h-10 sm:w-10',
        )}
      >
        <MoreHorizontal size={18} />
      </button>
      {open && pos && createPortal(
        <div
          ref={menuRef}
          role="menu"
          style={{ top: pos.top, right: pos.right }}
          className="fixed z-50 w-56 animate-scale-in rounded-xl border border-hairline bg-surface p-1.5 shadow-pop"
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
        </div>,
        document.body,
      )}
    </div>
  );
}
