import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Lưới FORM responsive chuẩn — dùng thay cho mọi `grid grid-cols-2/3` viết tay.
 *
 * Mobile 1 cột, chia cột từ `md` (768px). Ngưỡng md chứ không phải sm vì ở 640px
 * mỗi cột chỉ còn ~250px trong modal — quá hẹp cho `<Select>` nhãn tiếng Việt.
 */
export function FormGrid({
  cols = 2,
  gap = 4,
  children,
  className,
}: {
  cols?: 2 | 3 | 4;
  gap?: 3 | 4;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-1',
        gap === 3 ? 'gap-3' : 'gap-4',
        cols === 2 && 'md:grid-cols-2',
        cols === 3 && 'md:grid-cols-2 lg:grid-cols-3',
        cols === 4 && 'md:grid-cols-2 lg:grid-cols-4',
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Ô chiếm trọn chiều ngang lưới — thay cho `col-span-2` viết tay.
 * `col-span-full` an toàn với mọi số cột, kể cả khi đổi cấu hình FormGrid sau này.
 */
export function FormFull({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('md:col-span-full', className)}>{children}</div>;
}

/**
 * Lưới HIỂN THỊ read-only (label + value), không phải form nhập.
 *
 * Giữ ngưỡng `sm` (640px) chứ không phải `md`: nội dung chỉ là chữ ngắn nên
 * 2 cột ở 640px vẫn đọc tốt, khác form có control cần bề ngang.
 */
export function InfoGrid({
  cols = 2,
  children,
  className,
}: {
  cols?: 2 | 3;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-x-4 gap-y-2 text-sm',
        cols === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3',
        className,
      )}
    >
      {children}
    </div>
  );
}
