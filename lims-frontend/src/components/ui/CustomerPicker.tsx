import { useRef, useState } from 'react';
import { Check, Plus, Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import * as customersApi from '@/api/customers';
import type { Customer } from '@/types';

/**
 * Ô nhập tên khách hàng có tra cứu master data (m33).
 *
 * Cùng khuôn với phần chọn CHỈ TIÊU ở SampleFlow (m27): chọn từ danh mục HOẶC gõ
 * tự do. Không chọn ai ⇒ customerId = null ⇒ khách vãng lai, vẫn lưu phiếu được.
 *
 * Component KHÔNG tự điền các ô khác — nó trả nguyên bản ghi khách qua onPick để
 * bên gọi quyết định điền gì. Nhờ vậy dùng chung được cho cả phiếu nhận mẫu (điền
 * 6 ô) lẫn phiếu yêu cầu thử nghiệm (chỉ cần tên người gửi).
 */
export function CustomerPicker({
  name,
  customerId,
  onNameChange,
  onPick,
  onCreateNew,
  placeholder = 'Gõ tên khách hàng để tìm trong sổ…',
  autoFocus,
}: {
  /** Tên khách đang hiển thị trên phiếu (bản chụp, người dùng sửa đè được). */
  name: string;
  /** Đã liên kết khách nào trong sổ chưa. */
  customerId: string | null;
  /** Người dùng gõ tay ⇒ bên gọi phải bỏ liên kết (customer_id = null). */
  onNameChange: (name: string) => void;
  /** Chọn một khách trong sổ ⇒ bên gọi tự điền các ô liên quan. */
  onPick: (customer: Customer) => void;
  /** Có quyền thêm khách thì truyền vào; không truyền ⇒ ẩn nút (tránh bấm vào dính 403). */
  onCreateNew?: () => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const dq = useDebounced(name);
  const blurTimer = useRef<number | undefined>(undefined);

  // Đã chọn khách rồi thì thôi gợi ý — tránh nháy danh sách ngay sau khi chọn.
  const { data, loading } = useAsync(
    () =>
      open && !customerId && dq.trim().length >= 1
        ? customersApi.listCustomers({ q: dq.trim(), limit: 8 })
        : Promise.resolve(null),
    [dq, open, customerId],
  );
  const results = data?.data ?? [];
  const showPanel = open && !customerId && name.trim().length >= 1;

  return (
    <div className="relative">
      <div className="relative">
        <Search
          size={16}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stem"
        />
        <input
          value={name}
          autoFocus={autoFocus}
          placeholder={placeholder}
          onChange={(e) => onNameChange(e.target.value)}
          onFocus={() => setOpen(true)}
          // Blur chạy TRƯỚC click của tuỳ chọn ⇒ hoãn để onMouseDown kịp bắn.
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => setOpen(false), 120);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
          }}
          className={cn(
            'h-10 w-full rounded-lg border bg-surface pl-9 text-sm text-ink placeholder:text-stem/70',
            'focus:outline-none focus:ring-2 focus:ring-blueberry/30',
            customerId ? 'border-blueberry pr-9' : 'border-hairline pr-3',
          )}
        />
        {customerId && (
          <span
            title="Đã liên kết với khách hàng trong sổ"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-blueberry"
          >
            <Check size={16} />
          </span>
        )}
      </div>

      {showPanel && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-hairline bg-surface shadow-lg">
          {loading ? (
            <p className="px-3 py-2.5 text-sm text-subink">Đang tìm…</p>
          ) : results.length > 0 ? (
            <ul className="max-h-60 overflow-y-auto">
              {results.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    // mousedown chứ không phải click: blur của input xảy ra trước click.
                    onMouseDown={() => {
                      window.clearTimeout(blurTimer.current);
                      onPick(c);
                      setOpen(false);
                    }}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-plate"
                  >
                    <span className="text-sm font-medium text-ink">{c.name}</span>
                    {(c.address || c.phone || c.tax_code) && (
                      <span className="text-xs text-subink">
                        {[c.address, c.phone && `ĐT ${c.phone}`, c.tax_code && `MST ${c.tax_code}`]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2.5 text-sm text-subink">Không có khách hàng nào khớp</p>
          )}

          {onCreateNew && (
            <button
              type="button"
              onMouseDown={() => {
                window.clearTimeout(blurTimer.current);
                onCreateNew();
                setOpen(false);
              }}
              className="flex w-full items-center gap-1.5 border-t border-hairline px-3 py-2 text-left text-sm font-medium text-blueberry hover:bg-plate"
            >
              <Plus size={15} /> Thêm “{name.trim()}” vào sổ khách hàng
            </button>
          )}
        </div>
      )}

      {customerId ? (
        <button
          type="button"
          onClick={() => onNameChange(name)}
          className="mt-1.5 inline-flex items-center gap-1 text-xs text-subink hover:text-ink"
        >
          <X size={13} /> Bỏ liên kết, nhập tay
        </button>
      ) : (
        name.trim().length > 0 && (
          <p className="mt-1.5 text-xs text-subink">
            Chưa liên kết sổ khách hàng — phiếu vẫn lưu được (khách vãng lai).
          </p>
        )
      )}
    </div>
  );
}
