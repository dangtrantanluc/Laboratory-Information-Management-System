import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import { cn } from '@/lib/cn';

export function Field({
  label,
  required,
  error,
  hint,
  children,
  className,
}: {
  label?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label className="text-sm font-medium text-ink">
          {label}
          {required && <span className="ml-0.5 text-overdue">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-overdue">{error}</p>
      ) : hint ? (
        <p className="text-xs text-subink">{hint}</p>
      ) : null}
    </div>
  );
}

const baseControl =
  'h-10 w-full rounded-lg border bg-white px-3 text-sm text-ink placeholder:text-stem/70 transition-colors focus:outline-none focus:ring-2 focus:ring-blueberry/30 disabled:bg-plate disabled:cursor-not-allowed';

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }
>(function Input({ className, invalid, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(baseControl, invalid ? 'border-overdue' : 'border-hairline', className)}
      {...props}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }
>(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        baseControl,
        'h-auto min-h-[80px] py-2 leading-relaxed',
        invalid ? 'border-overdue' : 'border-hairline',
        className,
      )}
      {...props}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }
>(function Select({ className, invalid, children, ...props }, ref) {
  return (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          baseControl,
          'appearance-none pr-9',
          invalid ? 'border-overdue' : 'border-hairline',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <svg
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-stem"
        width="14"
        height="14"
        viewBox="0 0 20 20"
        fill="none"
      >
        <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    </div>
  );
});
