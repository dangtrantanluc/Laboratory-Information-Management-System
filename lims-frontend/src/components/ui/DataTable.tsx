import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useDown } from '@/lib/useMediaQuery';
import { CardSkeleton, EmptyState, TableSkeleton } from './States';

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Giá trị để sort (string|number). Bỏ qua nếu không sortable. */
  sortValue?: (row: T) => string | number;
  /** index = số thứ tự hiển thị (0-based, đã tính theo trang/sort hiện tại). */
  render: (row: T, index: number) => ReactNode;
  className?: string;
  headerClassName?: string;
  align?: 'left' | 'right' | 'center';

  /** Làm tiêu đề thẻ ở chế độ mobile. Không cột nào đặt → dùng cột đầu tiên. */
  primary?: boolean;
  /**
   * Độ ưu tiên khi thu hẹp (chỉ ảnh hưởng chế độ thẻ):
   * 1 = hiện ngay trên thẻ · 2 = ẩn sau "Xem thêm" (mặc định) · 3 = chỉ có ở bảng desktop.
   */
  priority?: 1 | 2 | 3;
  /** Nhãn dùng ở chế độ thẻ. Mặc định lấy `header` nếu nó là chuỗi. */
  mobileLabel?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  pageSize?: number;
  loading?: boolean;
  empty?: ReactNode;

  /** 'card' (mặc định) = dưới md đổi sang danh sách thẻ · 'scroll' = luôn giữ bảng. */
  mobileMode?: 'card' | 'scroll';
  /** Ghim cột đầu khi cuộn ngang ở desktop. Mặc định bật. */
  stickyFirstCol?: boolean;
  /** Cho người dùng đổi số dòng/trang. */
  pageSizeOptions?: number[];
}

type SortState = { key: string; dir: 'asc' | 'desc' } | null;

/**
 * Nhãn dùng ở chế độ thẻ. Trả '' cho cột hành động (`header: ''`) — những cột đó
 * không có nhãn, sẽ được render riêng ở đáy thẻ thay vì thành dòng "actions".
 */
function labelOf<T>(col: Column<T>): string {
  if (col.mobileLabel) return col.mobileLabel;
  if (typeof col.header === 'string') return col.header;
  return col.key;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  pageSize: initialPageSize = 8,
  loading,
  empty,
  mobileMode = 'card',
  stickyFirstCol = true,
  pageSizeOptions,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const isMobile = useDown('md');
  const asCards = mobileMode === 'card' && isMobile;

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const get = col.sortValue;
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      if (va < vb) return sort.dir === 'asc' ? -1 : 1;
      if (va > vb) return sort.dir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [rows, sort, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const offset = (safePage - 1) * pageSize;
  const pageRows = sorted.slice(offset, offset + pageSize);

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: 'asc' };
      if (prev.dir === 'asc') return { key, dir: 'desc' };
      return null;
    });
    setPage(1);
  }

  const body = asCards ? (
    loading ? (
      <CardSkeleton rows={pageSize} />
    ) : pageRows.length === 0 ? (
      (empty ?? <EmptyState />)
    ) : (
      <MobileCardList
        columns={columns}
        rows={pageRows}
        rowKey={rowKey}
        onRowClick={onRowClick}
        offset={offset}
      />
    )
  ) : (
    // Desktop: giữ nguyên hành vi cũ — thead vẫn hiện khi loading/rỗng để
    // người dùng thấy được bảng có những cột nào.
    <DesktopTable
      columns={columns}
      rows={pageRows}
      rowKey={rowKey}
      onRowClick={onRowClick}
      offset={offset}
      sort={sort}
      onToggleSort={toggleSort}
      stickyFirstCol={stickyFirstCol}
      loading={loading}
      empty={empty}
      skeletonRows={pageSize}
    />
  );

  return (
    <div className="flex flex-col">
      {body}

      {!loading && sorted.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-hairline px-4 py-3 text-xs text-subink sm:flex-row sm:items-center sm:justify-between">
          <span>
            Hiển thị{' '}
            <strong className="text-ink">
              {offset + 1}–{Math.min(offset + pageSize, sorted.length)}
            </strong>{' '}
            / {sorted.length} bản ghi
          </span>
          <div className="flex items-center gap-2">
            {pageSizeOptions && pageSizeOptions.length > 0 && (
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                aria-label="Số dòng mỗi trang"
                className="h-8 rounded-md border border-hairline bg-surface px-2 text-xs text-ink"
              >
                {pageSizeOptions.map((n) => (
                  <option key={n} value={n}>
                    {n} / trang
                  </option>
                ))}
              </select>
            )}
            <button
              disabled={safePage <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-hairline bg-surface text-stem hover:bg-plate disabled:opacity-40 sm:h-7 sm:w-7"
              aria-label="Trang trước"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="px-1 font-medium text-ink">
              {safePage} / {totalPages}
            </span>
            <button
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-hairline bg-surface text-stem hover:bg-plate disabled:opacity-40 sm:h-7 sm:w-7"
              aria-label="Trang sau"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ────────────────────────── Desktop: bảng ────────────────────────── */

function DesktopTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  offset,
  sort,
  onToggleSort,
  stickyFirstCol,
  loading,
  empty,
  skeletonRows,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  offset: number;
  sort: SortState;
  onToggleSort: (key: string) => void;
  stickyFirstCol: boolean;
  loading?: boolean;
  empty?: ReactNode;
  skeletonRows: number;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hasMoreRight, setHasMoreRight] = useState(false);

  // Gợi ý "còn nội dung bên phải" — bảng cuộn ngang không có affordance thì
  // người dùng không biết là mình đang thấy thiếu cột.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setHasMoreRight(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', update);
      ro.disconnect();
    };
  }, [columns.length, rows.length]);

  /** Cột đầu dính trái khi cuộn ngang → không mất ngữ cảnh dòng đang xem. */
  const stickyCell = (idx: number, isHeader: boolean) =>
    stickyFirstCol && idx === 0
      ? cn(
          'sticky left-0 z-[2]',
          isHeader ? 'bg-plate' : 'bg-surface',
          'after:absolute after:inset-y-0 after:-right-px after:w-px after:bg-hairline',
        )
      : undefined;

  return (
    <div className="relative">
      <div ref={scrollRef} className="overflow-x-auto scrollbar-thin">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-hairline bg-plate">
              {columns.map((col, idx) => {
                const active = sort?.key === col.key;
                const sortable = !!col.sortValue;
                return (
                  <th
                    key={col.key}
                    aria-sort={
                      !sortable
                        ? undefined
                        : active
                          ? sort?.dir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                    }
                    className={cn(
                      'whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-stem',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                      stickyCell(idx, true),
                      col.headerClassName,
                    )}
                  >
                    {sortable ? (
                      <button
                        onClick={() => onToggleSort(col.key)}
                        className={cn(
                          'inline-flex items-center gap-1 hover:text-ink',
                          col.align === 'right' && 'flex-row-reverse',
                          active && 'text-ink',
                        )}
                      >
                        {col.header}
                        {active ? (
                          sort?.dir === 'asc' ? (
                            <ChevronUp size={13} />
                          ) : (
                            <ChevronDown size={13} />
                          )
                        ) : (
                          <ChevronsUpDown size={13} className="opacity-50" />
                        )}
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  <TableSkeleton rows={skeletonRows} cols={columns.length} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  {empty ?? <EmptyState />}
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(
                  'group bg-surface transition-colors hover:bg-plate/70',
                  onRowClick && 'cursor-pointer',
                )}
              >
                {columns.map((col, idx) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3 align-middle text-ink',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                      stickyCell(idx, false),
                      // Ô dính phải đổi nền theo hover của dòng, nếu không sẽ
                      // lệch màu với phần còn lại khi rê chuột.
                      stickyFirstCol && idx === 0 && 'group-hover:bg-plate/70',
                      col.className,
                    )}
                  >
                    {col.render(row, offset + i)}
                  </td>
                ))}
              </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {hasMoreRight && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-surface to-transparent"
        />
      )}
    </div>
  );
}

/* ────────────────────────── Mobile: danh sách thẻ ────────────────────────── */

function MobileCardList<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  offset,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  offset: number;
}) {
  const primaryCol = columns.find((c) => c.primary) ?? columns[0];
  const rest = columns.filter((c) => c !== primaryCol);
  // Cột không có nhãn (`header: ''`) là cột hành động → luôn hiện ở đáy thẻ,
  // không nhét vào "Xem thêm" và không render nhãn "actions".
  const actions = rest.filter((c) => labelOf(c) === '');
  const labelled = rest.filter((c) => labelOf(c) !== '');
  const shown = labelled.filter((c) => (c.priority ?? 2) === 1);
  const hidden = labelled.filter((c) => (c.priority ?? 2) === 2);

  return (
    <ul className="divide-y divide-hairline">
      {rows.map((row, i) => (
        <MobileCard
          key={rowKey(row)}
          row={row}
          index={offset + i}
          primaryCol={primaryCol}
          shown={shown}
          hidden={hidden}
          actions={actions}
          onClick={onRowClick}
        />
      ))}
    </ul>
  );
}

function MobileCard<T>({
  row,
  index,
  primaryCol,
  shown,
  hidden,
  actions,
  onClick,
}: {
  row: T;
  index: number;
  primaryCol: Column<T>;
  shown: Column<T>[];
  hidden: Column<T>[];
  actions: Column<T>[];
  onClick?: (row: T) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const pairs = (cols: Column<T>[]) =>
    cols.map((c) => (
      <Fragment key={c.key}>
        <dt className="pt-0.5 text-xs font-medium uppercase tracking-wide text-stem">
          {labelOf(c)}
        </dt>
        <dd className="min-w-0 text-ink">{c.render(row, index)}</dd>
      </Fragment>
    ));

  return (
    <li>
      <div
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={onClick ? () => onClick(row) : undefined}
        onKeyDown={
          onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onClick(row);
                }
              }
            : undefined
        }
        className={cn(
          'flex flex-col gap-2 bg-surface px-4 py-3.5 transition-colors',
          onClick && 'cursor-pointer active:bg-plate/70',
        )}
      >
        <div className="text-sm font-semibold text-ink">{primaryCol.render(row, index)}</div>

        {shown.length > 0 && (
          <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
            {pairs(shown)}
          </dl>
        )}

        {hidden.length > 0 && (
          <>
            {expanded && (
              <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1.5 border-t border-hairline pt-2 text-sm">
                {pairs(hidden)}
              </dl>
            )}
            <button
              onClick={(e) => {
                // Không được kích hoạt onRowClick của thẻ cha
                e.stopPropagation();
                setExpanded((v) => !v);
              }}
              aria-expanded={expanded}
              className="-mx-1 self-start rounded px-1 py-1 text-xs font-medium text-blueberry"
            >
              {expanded ? 'Thu gọn' : `Xem thêm (${hidden.length})`}
            </button>
          </>
        )}

        {/* Cột hành động: luôn hiện ở đáy thẻ, không nhãn. Các trang đều đã
            stopPropagation ở wrapper nút nên không kích hoạt onRowClick. */}
        {actions.length > 0 && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-hairline pt-2">
            {actions.map((c) => (
              <div key={c.key}>{c.render(row, index)}</div>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}
