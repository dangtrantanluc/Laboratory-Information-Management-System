import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'danger' | 'success' | 'ghost';
type Size = 'sm' | 'md' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Chiếm trọn chiều ngang dưới sm — dùng cho nút chính trong form/modal/PageHeader. */
  fullWidthMobile?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-blueberry text-white hover:bg-blueberry/90 active:bg-blueberry shadow-sm',
  secondary: 'bg-surface text-ink border border-hairline hover:bg-plate active:bg-plate',
  danger: 'bg-overdue text-white hover:bg-overdue/90 shadow-sm',
  success: 'bg-success text-white hover:bg-success/90 shadow-sm',
  ghost: 'bg-transparent text-stem hover:bg-plate hover:text-ink',
};

// Cao hơn trên mobile để đạt vùng chạm khuyến nghị (~40–44px), thu về kích thước
// gốc từ sm trở lên nơi con trỏ chính xác.
const SIZES: Record<Size, string> = {
  sm: 'h-9 px-3 text-xs gap-1.5 sm:h-8',
  md: 'h-11 px-4 text-sm gap-2 sm:h-10',
  icon: 'h-10 w-10 p-0 sm:h-9 sm:w-9',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading,
    disabled,
    className,
    children,
    fullWidthMobile,
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blueberry/40',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        fullWidthMobile && 'w-full sm:w-auto',
        className,
      )}
      {...props}
    >
      {loading && <Loader2 size={size === 'sm' ? 14 : 16} className="animate-spin" />}
      {children}
    </button>
  );
});
