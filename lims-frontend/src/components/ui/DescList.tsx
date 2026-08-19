import type { ReactNode } from 'react';
import { ArrowRight, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Avatar } from '@/components/ui/Avatar';
import { formatDate } from '@/lib/format';

/**
 * Bộ dựng modal XEM CHI TIẾT.
 *
 * VÌ SAO THIẾT KẾ LẠI (m34): bản cũ là một lưới phẳng label/value, tối đa 3 cột.
 * Ba vấn đề lộ rõ khi các bảng NCKH có thêm cột:
 *   1. Không có phân cấp — "Kinh phí 100.000.000 VND" đọc ngang hàng "Phòng ban".
 *      Người dùng phải đọc hết 12 ô mới biết đâu là thông tin chính.
 *   2. Lưới 3 cột làm nhịp hàng gãy: ô ngày tháng chỉ 10 ký tự nằm cạnh ô "Đơn vị
 *      phối hợp" dài 3 dòng, kéo cả hàng cao lên và để lại khoảng trắng lệch.
 *   3. Cặp Bắt đầu/Kết thúc chiếm 2 ô để diễn đạt MỘT sự việc (khoảng thời gian).
 *
 * Cách chữa: rút về 2 cột (giá trị có chỗ thở), thêm dải tóm tắt ở đầu cho thông
 * tin nhận dạng, gộp nhóm theo chủ đề, và cho vài kiểu giá trị hay gặp một hình
 * thức riêng (khoảng thời gian, liên kết minh chứng, danh sách người).
 */

/* ────────────────────────────────── Dải tóm tắt đầu modal ────────────────── */

/**
 * Dải nhận dạng: trạng thái/phân loại bên trái, con số chủ đạo bên phải.
 *
 * Đây là thứ trả lời "bản ghi này là gì" trong một cái liếc. Con số (kinh phí,
 * giá trị hợp đồng) tách hẳn khỏi lưới label/value vì nó là thông tin người dùng
 * tìm nhiều nhất — để chung trong lưới là chôn nó.
 */
export function DetailHero({
  chips,
  metricLabel,
  metric,
  className,
}: {
  chips?: ReactNode;
  metricLabel?: string;
  metric?: ReactNode;
  className?: string;
}) {
  const hasMetric = metric !== null && metric !== undefined && metric !== '' && metric !== '—';
  if (!chips && !hasMetric) return null;
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-xl border border-hairline bg-plate/70 px-4 py-3.5',
        className,
      )}
    >
      {chips && <div className="flex flex-wrap items-center gap-2">{chips}</div>}
      {hasMetric && (
        <div className="text-right max-sm:text-left">
          {metricLabel && (
            <p className="text-[11px] font-semibold uppercase tracking-wide text-stem">{metricLabel}</p>
          )}
          <p className="text-lg font-semibold tabular-nums text-ink">{metric}</p>
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────── Nhóm & lưới ──────────────────────────── */

/** Nhóm trường theo chủ đề. Bỏ qua nhóm rỗng để modal thưa không bị "thủng". */
export function DescSection({
  title,
  children,
  className,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('flex flex-col gap-3', className)}>
      {title && (
        <div className="flex items-center gap-3">
          <h3 className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-berry">
            {title}
          </h3>
          <span aria-hidden className="h-px flex-1 bg-hairline" />
        </div>
      )}
      {children}
    </section>
  );
}

/** Danh sách mô tả read-only (label + value). */
export function DescList({
  children,
  className,
  cols = 2,
}: {
  children: ReactNode;
  className?: string;
  /** 1 cột cho nội dung dài (mô tả, nhận xét); mặc định 2. */
  cols?: 1 | 2;
}) {
  // Ngoại lệ của quy ước "2 cột từ md": nội dung read-only ngắn nên 2 cột ở 640px
  // vẫn đọc tốt — khác form có <Select>/<Input> cần bề ngang.
  // KHÔNG lên 3 cột ở màn rộng: giá trị dài (tên đơn vị, tên tạp chí) bị bóp còn
  // ~200px và xuống 3 dòng, làm nhịp hàng gãy hơn là tiết kiệm được chiều cao.
  return (
    <dl
      className={cn(
        'grid grid-cols-1 gap-x-8 gap-y-4',
        cols === 2 && 'sm:grid-cols-2',
        className,
      )}
    >
      {children}
    </dl>
  );
}

export function DescItem({
  label,
  value,
  full,
  emphasis,
}: {
  label: ReactNode;
  value: ReactNode;
  /** Chiếm trọn hàng (dùng cho nội dung dài). */
  full?: boolean;
  /** Giá trị quan trọng — to và đậm hơn phần còn lại. */
  emphasis?: boolean;
}) {
  const empty = value === null || value === undefined || value === '' || value === '—';
  return (
    <div className={cn('min-w-0', full && 'sm:col-span-2')}>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-stem">{label}</dt>
      <dd
        className={cn(
          'mt-1 break-words',
          emphasis ? 'text-base font-semibold tabular-nums' : 'text-sm',
          empty ? 'font-normal text-stem' : 'text-ink',
        )}
      >
        {empty ? 'Chưa có' : value}
      </dd>
    </div>
  );
}

/* ────────────────────────────────── Kiểu giá trị hay gặp ─────────────────── */

/**
 * Khoảng thời gian trong MỘT ô thay vì hai ô Bắt đầu/Kết thúc.
 *
 * Hai mốc là một sự việc; tách đôi vừa tốn ô vừa bắt người đọc tự ghép lại. Mũi
 * tên làm quan hệ trước–sau hiện ra mà không cần chữ.
 */
export function DescPeriod({
  label = 'Thời gian',
  from,
  to,
  full,
}: {
  label?: string;
  from?: string | null;
  to?: string | null;
  full?: boolean;
}) {
  if (!from && !to) return <DescItem label={label} value={null} full={full} />;
  return (
    <DescItem
      label={label}
      full={full}
      value={
        <span className="inline-flex flex-wrap items-center gap-1.5 tabular-nums">
          <span>{from ? formatDate(from) : '—'}</span>
          <ArrowRight size={13} className="shrink-0 text-stem" aria-label="đến" />
          <span>{to ? formatDate(to) : '—'}</span>
        </span>
      }
    />
  );
}

/**
 * Liên kết minh chứng dạng chip.
 *
 * URL Drive/DOI dài 80-120 ký tự; in nguyên văn thì xuống 2-3 dòng và vẫn không
 * ai đọc. Chip hiện TÊN MIỀN (drive.google.com) — đủ để biết minh chứng nằm ở
 * đâu — còn URL đầy đủ nằm ở tooltip và href.
 */
export function DescLink({
  label = 'Link minh chứng',
  url,
  full = true,
}: {
  label?: string;
  url?: string | null;
  full?: boolean;
}) {
  if (!url) return <DescItem label={label} value={null} full={full} />;
  let host = url;
  try {
    host = new URL(url).hostname.replace(/^www\./, '');
  } catch {
    /* URL không hợp lệ (người dùng dán tay) — hiện nguyên văn, vẫn bấm được */
  }
  return (
    <DescItem
      label={label}
      full={full}
      value={
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          title={url}
          className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-hairline bg-surface2 px-2.5 py-1.5 text-sm text-blueberry transition-colors hover:border-blueberry/40 hover:bg-plate focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blueberry"
        >
          <ExternalLink size={13} className="shrink-0" />
          <span className="truncate">{host}</span>
        </a>
      }
    />
  );
}

export type DescPerson = {
  name: string;
  /** Nhãn vai trò hiện bên phải (Chủ nhiệm, Tác giả liên hệ…). */
  role?: string | null;
  /** Người ngoài hệ thống — đánh dấu để phân biệt với tài khoản nội bộ. */
  external?: boolean;
};

/**
 * Danh sách người tham gia dạng thẻ.
 *
 * Bản cũ là danh sách kẻ ngang chữ trơn — với 10+ thành viên (đề tài cấp Bộ có
 * tới 12) thì thành một khối chữ đặc. Thẻ có ảnh đại diện chữ cái cho phép quét
 * theo hàng và xuống dòng tự nhiên theo bề ngang.
 */
export function DescPeople({
  label,
  people,
  emptyText = 'Chưa có',
}: {
  label: string;
  people: DescPerson[];
  emptyText?: string;
}) {
  return (
    <div className="sm:col-span-2">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-stem">
        {label}
        {people.length > 0 && <span className="ml-1.5 font-normal text-stem">({people.length})</span>}
      </dt>
      <dd className="mt-2">
        {people.length === 0 ? (
          <span className="text-sm text-stem">{emptyText}</span>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {people.map((p, i) => (
              <li
                key={`${p.name}-${i}`}
                className="flex min-w-0 items-center gap-2 rounded-full border border-hairline bg-surface2 py-1 pl-1 pr-3"
              >
                <Avatar name={p.name} size="sm" />
                <span className="min-w-0">
                  <span className="block truncate text-sm text-ink">{p.name}</span>
                  {(p.role || p.external) && (
                    <span className="block truncate text-[11px] leading-tight text-stem">
                      {[p.role, p.external ? 'ngoài hệ thống' : null].filter(Boolean).join(' · ')}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}
