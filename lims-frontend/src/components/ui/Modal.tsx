import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useDown } from '@/lib/useMediaQuery';
import { useFocusTrap, useBodyScrollLock } from '@/lib/useFocusTrap';

/**
 * Hộp thoại.
 *
 * ≥sm: hộp thoại giữa màn hình như thường lệ.
 * <sm: bottom-sheet toàn chiều ngang, trượt lên từ đáy — trên màn 360×640 hộp
 *      thoại kiểu cũ chỉ còn ~380px vùng nhập liệu và footer trôi khỏi tầm nhìn.
 *
 * Bố cục flex-col + `min-h-0 flex-1` ở body giữ footer LUÔN dính đáy panel mà
 * không cần position:sticky.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const isMobile = useDown('sm');

  // Dùng hook có đếm tham chiếu: ConfirmDialog thường mở BÊN TRONG một Modal,
  // nếu mỗi lớp tự set body.style.overflow thì lớp con đóng lại sẽ mở khoá cuộn
  // trong khi lớp cha vẫn đang mở.
  useBodyScrollLock(open);
  useFocusTrap(panelRef, open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Dùng w-[min(92vw,…)] thay max-w-*: modal `lg` cũ (max-w-3xl = 768px) rộng
  // đúng bằng viewport iPad dọc nên dán sát hai mép.
  const widths: Record<string, string> = {
    sm: 'sm:w-[min(92vw,28rem)]',
    md: 'sm:w-[min(92vw,36rem)]',
    lg: 'sm:w-[min(92vw,48rem)]',
    xl: 'sm:w-[min(94vw,64rem)]',
  };

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-50 flex overflow-y-auto',
        isMobile ? 'items-end' : 'items-start justify-center p-4 sm:p-6',
      )}
    >
      <div
        className="fixed inset-0 animate-fade-in bg-blueberry/30 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          'relative z-10 flex w-full flex-col border-hairline bg-surface shadow-pop',
          isMobile
            ? 'max-h-sheet animate-slide-up rounded-t-2xl border-t pb-safe'
            : cn('my-8 animate-scale-in rounded-xl border', widths[size]),
        )}
      >
        {/* Tay nắm kéo — tín hiệu thị giác "đây là sheet kéo được từ đáy" */}
        {isMobile && (
          <div aria-hidden className="mx-auto mt-2.5 h-1 w-10 shrink-0 rounded-full bg-hairline" />
        )}

        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-hairline px-4 py-3.5 sm:px-5 sm:py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-ink">
              {title}
            </h2>
            {description && <p className="mt-0.5 text-sm text-subink">{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="-mr-1 shrink-0 rounded-lg p-2 text-stem hover:bg-plate hover:text-ink"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </div>

        <div
          className={cn(
            'min-h-0 flex-1 overflow-y-auto px-4 py-4 scrollbar-thin sm:px-5',
            !isMobile && 'max-h-[70vh]',
          )}
        >
          {children}
        </div>

        {footer && (
          // max-sm:[&>button]:flex-1 → 2 nút Hủy/Lưu chia đôi chiều ngang, dễ chạm
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-hairline bg-plate/60 px-4 py-3 max-sm:[&>button]:flex-1 sm:px-5 sm:py-3.5">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
