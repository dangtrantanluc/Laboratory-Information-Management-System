import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Nhóm trường trong modal NHẬP LIỆU — đối xứng với `DescSection` ở phía xem.
 *
 * VÌ SAO CẦN: 17/18 modal form từ 7 ô trở lên đang đổ tất cả vào MỘT lưới 2 cột
 * phẳng, không tiêu đề, không phân đoạn. Với form 13 ô (thêm công bố khoa học) thì
 * "Số đơn" nằm sát "Năm học" mà hai thứ đó chẳng liên quan gì nhau — người nhập
 * phải đọc hết nhãn mới biết mình đang ở phần nào của biểu mẫu.
 *
 * DÙNG LẠI ĐÚNG NGÔN NGỮ THỊ GIÁC của DescSection (chữ hoa nhỏ màu sage + gạch
 * hairline) là chủ ý: cùng một bản ghi, mặt xem và mặt nhập phải trông là một hệ.
 * Nếu hai bên khác nhau thì người dùng phải học hai bố cục cho cùng một thứ.
 *
 * KHÔNG tự dựng <form>/<fieldset>: các modal hiện có tự quản lý submit qua nút ở
 * footer, chèn thêm tầng form sẽ đổi hành vi Enter/validate của chúng.
 */
export function FormSection({
  title,
  hint,
  children,
  cols = 2,
  className,
}: {
  title?: string;
  /** Câu giải thích cho CẢ nhóm — thay vì lặp hint ở từng ô. */
  hint?: string;
  children: ReactNode;
  /** 1 cột cho nhóm có nội dung dài (mô tả, danh sách con); mặc định 2. */
  cols?: 1 | 2;
  className?: string;
}) {
  return (
    <section className={cn('flex flex-col gap-3', className)}>
      {title && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h3 className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-berry">
              {title}
            </h3>
            <span aria-hidden className="h-px flex-1 bg-hairline" />
          </div>
          {hint && <p className="text-xs text-subink">{hint}</p>}
        </div>
      )}
      <div className={cn('grid grid-cols-1 gap-4', cols === 2 && 'md:grid-cols-2')}>
        {children}
      </div>
    </section>
  );
}

/**
 * Khung ngoài của thân modal form: xếp các FormSection theo chiều dọc.
 *
 * Tách riêng thay vì để mỗi trang tự viết `<div className="flex flex-col gap-6">`
 * — khoảng cách giữa các nhóm là một quyết định thiết kế, không nên mỗi nơi một số.
 */
export function FormBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('flex flex-col gap-6', className)}>{children}</div>;
}
