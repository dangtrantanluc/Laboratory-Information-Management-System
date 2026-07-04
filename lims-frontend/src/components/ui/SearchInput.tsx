import { Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';

export function SearchInput({
  value,
  onChange,
  placeholder = 'Tìm kiếm…',
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn('relative', className)}>
      <Search
        size={16}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stem"
      />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-hairline bg-white pl-9 pr-9 text-sm text-ink placeholder:text-stem/70 focus:outline-none focus:ring-2 focus:ring-blueberry/30"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-stem hover:bg-plate"
          aria-label="Xóa tìm kiếm"
        >
          <X size={15} />
        </button>
      )}
    </div>
  );
}
