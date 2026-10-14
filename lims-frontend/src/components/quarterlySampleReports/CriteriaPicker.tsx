/**
 * Chọn chỉ tiêu phân tích từ danh mục — lọc theo ĐÚNG loại mẫu (danh mục có 75 tên trùng
 * giữa các loại mẫu, vd "Độ ẩm" của Đất và của Phân bón, nên không chọn trong danh sách phẳng).
 * Dùng chung cho form một mẫu và form nhập nhiều mẫu.
 */
import { useState } from 'react';
import { X } from 'lucide-react';
import { Input } from '@/components/ui/Field';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { listTestParameters } from '@/api/sampleFlow';
import { TEST_MATRIX_LABELS, type TestMatrix } from '@/types';

/** id → tên. Giữ cả chỉ tiêu đã chọn nhưng không nằm trong kết quả tìm hiện tại. */
export type SelectedCriteria = Map<string, string>;

export function toggleCriterion(prev: SelectedCriteria, id: string, name: string): SelectedCriteria {
  const next = new Map(prev);
  if (next.has(id)) next.delete(id);
  else next.set(id, name);
  return next;
}

export function CriteriaPicker({
  matrix,
  selected,
  onToggle,
}: {
  matrix: TestMatrix;
  selected: SelectedCriteria;
  onToggle: (id: string, name: string) => void;
}) {
  const [search, setSearch] = useState('');
  const dq = useDebounced(search);
  const { data, loading } = useAsync(
    () =>
      listTestParameters({
        matrix: matrix === 'other' ? undefined : matrix,
        q: dq || undefined,
        is_active: true,
        limit: 100,
      }),
    [matrix, dq],
  );
  const options = data?.data ?? [];

  return (
    <div className="flex flex-col gap-2">
      {selected.size > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {[...selected].map(([id, name]) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-full bg-blueberry/10 py-0.5 pl-2.5 pr-1 text-xs font-medium text-blueberry"
            >
              {name}
              <button
                type="button"
                aria-label={`Bỏ ${name}`}
                onClick={() => onToggle(id, name)}
                className="rounded-full p-0.5 hover:bg-blueberry/20"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={`Tìm chỉ tiêu trong danh mục ${matrix === 'other' ? '' : TEST_MATRIX_LABELS[matrix]}…`}
      />
      <div className="max-h-56 overflow-y-auto rounded-lg border border-hairline">
        {loading ? (
          <p className="px-3 py-2 text-sm text-subink">Đang tải…</p>
        ) : options.length === 0 ? (
          <p className="px-3 py-2 text-sm text-subink">
            Không có chỉ tiêu phù hợp — ghi vào ô "Chỉ tiêu ngoài danh mục" bên dưới.
          </p>
        ) : (
          options.map((p) => (
            <label
              key={p.id}
              className="flex cursor-pointer items-start gap-2 border-b border-hairline px-3 py-1.5 text-sm last:border-0 hover:bg-plate"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={selected.has(p.id)}
                onChange={() => onToggle(p.id, p.name)}
              />
              <span className="min-w-0">
                <span className="text-ink">{p.name}</span>
                {(p.method || matrix === 'other') && (
                  <span className="block text-xs text-subink">
                    {[matrix === 'other' ? p.matrix_label : null, p.method].filter(Boolean).join(' · ')}
                  </span>
                )}
              </span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
