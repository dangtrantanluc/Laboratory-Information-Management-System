import { useState, type ReactNode } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from './Button';
import { Modal } from './Modal';
import { useDown } from '@/lib/useMediaQuery';

export interface FilterSpec {
  /** Khoá duy nhất trong danh sách. */
  key: string;
  /** Control lọc — thường là `<Select>`. KHÔNG đặt max-w cứng, bề rộng do FilterBar quyết định. */
  node: ReactNode;
  /** Nhãn hiện trong sheet lọc ở mobile. */
  label: string;
  /** true khi filter đang có giá trị khác mặc định — dùng để đếm và hiện nút "Xoá lọc". */
  active: boolean;
}

/**
 * Thanh lọc chuẩn cho trang danh sách.
 *
 * ≥md: ô tìm + các control xếp ngang, bề rộng đều nhau (clamp) thay vì mỗi trang
 *      tự đặt `max-w-[160px]`/`max-w-[200px]` khiến chúng so le.
 * <md: chỉ hiện ô tìm + nút "Lọc (n)", các control nằm trong bottom-sheet.
 */
export function FilterBar({
  search,
  filters = [],
  onClear,
  extra,
  className,
}: {
  search?: ReactNode;
  filters?: FilterSpec[];
  onClear?: () => void;
  /** Nội dung phụ ghim cuối thanh (nút xuất Excel, chuyển chế độ xem…). */
  extra?: ReactNode;
  className?: string;
}) {
  const isMobile = useDown('md');
  const [sheetOpen, setSheetOpen] = useState(false);
  const activeCount = filters.filter((f) => f.active).length;

  if (isMobile) {
    return (
      <>
        <div className={cn('flex items-center gap-2 border-b border-hairline p-3', className)}>
          {search && <div className="min-w-0 flex-1">{search}</div>}
          {filters.length > 0 && (
            <Button
              variant="secondary"
              onClick={() => setSheetOpen(true)}
              className="shrink-0"
              aria-label={`Bộ lọc${activeCount > 0 ? ` (${activeCount} đang bật)` : ''}`}
            >
              <SlidersHorizontal size={15} />
              Lọc
              {activeCount > 0 && (
                <span className="ml-0.5 rounded-full bg-blueberry px-1.5 text-[11px] font-bold text-white">
                  {activeCount}
                </span>
              )}
            </Button>
          )}
          {extra}
        </div>

        <Modal
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          title="Bộ lọc"
          footer={
            <>
              {onClear && activeCount > 0 && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    onClear();
                    setSheetOpen(false);
                  }}
                >
                  <X size={15} /> Xoá lọc
                </Button>
              )}
              <Button onClick={() => setSheetOpen(false)}>Áp dụng</Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            {filters.map((f) => (
              <label key={f.key} className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-ink">{f.label}</span>
                {f.node}
              </label>
            ))}
          </div>
        </Modal>
      </>
    );
  }

  return (
    <div className={cn('flex flex-wrap items-center gap-3 border-b border-hairline p-4', className)}>
      {search && <div className="min-w-[220px] max-w-sm flex-1">{search}</div>}
      {filters.map((f) => (
        <div key={f.key} className="w-[clamp(150px,18vw,220px)]">
          {f.node}
        </div>
      ))}
      {onClear && activeCount > 0 && (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X size={14} /> Xoá lọc ({activeCount})
        </Button>
      )}
      {extra && <div className="ml-auto flex items-center gap-2">{extra}</div>}
    </div>
  );
}
