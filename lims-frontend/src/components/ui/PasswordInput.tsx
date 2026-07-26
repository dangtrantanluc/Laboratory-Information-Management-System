import { forwardRef, useId, useState, type InputHTMLAttributes } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Input } from './Field';

/**
 * Ô nhập mật khẩu có nút hiện/ẩn.
 *
 * Gõ sai mật khẩu mà không thấy mình gõ gì là nguyên nhân phổ biến nhất của
 * "đăng nhập không được" — nhất là với mật khẩu sinh ngẫu nhiên dài, trên điện
 * thoại, hoặc khi bàn phím đang ở chế độ khác.
 *
 * Vì sao là component dùng chung: dự án có 6 trang chứa ô mật khẩu (Login,
 * Register, Settings, Users, ResetPassword, ChangePassword). Gắn nút vào từng
 * trang là 6 bản sao của cùng một logic, và bản nào sửa sót sẽ lệch hành vi.
 */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { invalid?: boolean }
>(function PasswordInput({ className, invalid, disabled, ...props }, ref) {
  const [visible, setVisible] = useState(false);
  const hintId = useId();

  return (
    <div className="relative">
      <Input
        ref={ref}
        // Đổi type thay vì dùng CSS: trình duyệt và trình quản lý mật khẩu dựa
        // vào type="password" để nhận diện trường, nên phải giữ đúng ngữ nghĩa.
        type={visible ? 'text' : 'password'}
        invalid={invalid}
        disabled={disabled}
        // Chừa chỗ cho nút, tránh chữ chạy xuống dưới biểu tượng.
        className={cn('pr-11', className)}
        aria-describedby={hintId}
        {...props}
      />
      <button
        type="button"
        // type="button" là BẮT BUỘC: mặc định <button> trong <form> là submit,
        // nên thiếu nó thì bấm con mắt sẽ gửi luôn biểu mẫu đăng nhập.
        onClick={() => setVisible((v) => !v)}
        disabled={disabled}
        // tabIndex={-1}: người dùng bàn phím nhấn Tab từ ô mật khẩu là muốn tới
        // nút Đăng nhập, không phải dừng ở nút phụ trợ này.
        tabIndex={-1}
        aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        aria-pressed={visible}
        className={cn(
          'absolute right-1 top-1/2 -translate-y-1/2 grid h-8 w-8 place-items-center rounded-md',
          'text-subink transition-colors hover:text-ink hover:bg-plate',
          'focus:outline-none focus:ring-2 focus:ring-blueberry/30',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
      <span id={hintId} className="sr-only">
        {visible ? 'Mật khẩu đang hiển thị' : 'Mật khẩu đang được che'}
      </span>
    </div>
  );
});
