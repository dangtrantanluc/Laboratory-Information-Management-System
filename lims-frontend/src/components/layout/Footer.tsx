import { useState } from 'react';
import { MapPin, Phone, Printer, Mail, Facebook, Leaf, Eye, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useAsync } from '@/lib/useAsync';
import { formatNumber } from '@/lib/format';
import * as reportingApi from '@/api/reporting';

interface Counters {
  today?: number;
  week?: number;
  month?: number;
  total?: number;
}

/**
 * Chân trang — vibe Viện Sinh học (xanh lá + hoạ tiết lá).
 *
 * ≥md: bố cục 3 CỘT (Thông tin Viện | Liên hệ | Lượt truy cập) như thiết kế gốc.
 * <md: thu về 1 dòng gọn + accordion "Liên hệ" — trên mobile bố cục 3 cột xếp dọc
 *      thành ~300px, quá tốn chỗ cho nội dung phụ trợ.
 */
export function Footer() {
  const { data } = useAsync(() => reportingApi.getAccessCounters(), []);
  const c = data?.data;
  const [expanded, setExpanded] = useState(false);

  return (
    <footer className="relative shrink-0 overflow-hidden bg-gradient-to-r from-blueberry to-berry text-white/90 shadow-[0_-1px_3px_rgba(0,0,0,0.08)]">
      {/* Hoạ tiết lá mờ — vibe sinh học */}
      <Leaf
        aria-hidden
        strokeWidth={0.6}
        className="pointer-events-none absolute -right-6 -top-14 h-44 w-44 rotate-12 text-white/[0.06]"
      />

      {/* ── <md: 1 dòng gọn + accordion ── */}
      <div className="relative px-4 py-3 pb-safe text-xs md:hidden">
        <div className="flex items-center gap-2.5">
          <img
            src="/ribe-logo.jpeg"
            alt="RIBE"
            className="h-8 w-8 shrink-0 rounded-full bg-white object-contain ring-1 ring-white/50"
          />
          <p className="min-w-0 flex-1 truncate font-bold uppercase tracking-wide text-yogurt">
            Viện CNSH &amp; Môi trường
          </p>
          <button
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex shrink-0 items-center gap-1 rounded-md bg-white/15 px-2.5 py-1.5 font-medium text-white transition-colors hover:bg-white/25"
          >
            Liên hệ
            <ChevronDown size={13} className={cn('transition-transform', expanded && 'rotate-180')} />
          </button>
        </div>
        {expanded && (
          <div className="mt-3 flex flex-col gap-4 border-t border-white/15 pt-3">
            <InstituteAddress />
            <ContactList />
            <VisitCounters counters={c} withHeading />
          </div>
        )}
      </div>

      {/* ── ≥md: 3 cột như thiết kế gốc ── */}
      <div className="relative hidden gap-x-10 gap-y-4 px-4 py-3.5 text-xs md:grid lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1fr)] lg:px-8">
        {/* ── CỘT 1: Thông tin Viện ── */}
        <div className="flex min-w-0 gap-3">
          <img
            src="/ribe-logo.jpeg"
            alt="RIBE"
            className="h-11 w-11 shrink-0 rounded-full bg-white object-contain ring-1 ring-white/50"
          />
          <InstituteAddress />
        </div>

        {/* ── CỘT 2: Liên hệ ── */}
        <div className="flex min-w-0 flex-col border-white/15 lg:border-l lg:pl-10">
          <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-yogurt">Liên hệ</p>
          <ContactList />
        </div>

        {/* ── CỘT 3: Lượt truy cập ── */}
        <div className="flex min-w-0 flex-col border-white/15 lg:border-l lg:pl-10">
          <VisitCounters counters={c} withHeading />
        </div>
      </div>
    </footer>
  );
}

function InstituteAddress() {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 leading-snug">
      <p className="font-bold uppercase tracking-wide text-yogurt">
        Viện Nghiên cứu Công nghệ Sinh học và Môi trường
      </p>
      <p className="text-white/75">Trường Đại học Nông Lâm TP. Hồ Chí Minh</p>
      <p className="flex items-start gap-1.5 text-white/65">
        <MapPin size={11} className="mt-0.5 shrink-0 text-yogurt" />
        <span>Khu phố 33, P. Linh Xuân, TP. Hồ Chí Minh</span>
      </p>
      <p className="text-[11px] text-white/50">Phân hiệu Gia Lai · Phân hiệu Ninh Thuận</p>
    </div>
  );
}

function ContactList() {
  return (
    <ul className="flex flex-col gap-1">
      <li>
        <a
          href="tel:02837220294"
          className="flex items-center gap-2 py-0.5 text-white/85 hover:text-white"
        >
          <Phone size={12} className="shrink-0 text-yogurt" /> 028 3722 0294
        </a>
      </li>
      <li className="flex items-center gap-2 py-0.5 text-white/85" title="Số fax">
        <Printer size={12} className="shrink-0 text-yogurt" /> 028 3724 6019
      </li>
      <li className="min-w-0">
        <a
          href="mailto:vphanhchinh@hcmuaf.edu.vn"
          className="flex min-w-0 items-center gap-2 py-0.5 text-white/85 hover:text-white"
        >
          <Mail size={12} className="shrink-0 text-yogurt" />
          <span className="truncate">vphanhchinh@hcmuaf.edu.vn</span>
        </a>
      </li>
      <li>
        <a
          href="https://www.facebook.com/NongLamUniversity"
          target="_blank"
          rel="noopener noreferrer"
          title="Fanpage Trường Đại học Nông Lâm TP.HCM"
          className="inline-flex items-center gap-2 rounded-md bg-white/15 px-2 py-1 font-medium text-white transition-colors hover:bg-white/25"
        >
          <Facebook size={12} /> Facebook
        </a>
      </li>
    </ul>
  );
}

function VisitCounters({ counters, withHeading }: { counters?: Counters; withHeading?: boolean }) {
  return (
    <>
      {withHeading && (
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-yogurt">
          <Eye size={12} /> Lượt truy cập
        </p>
      )}
      <ul className="flex flex-col gap-1">
        <Counter label="Trong ngày" value={counters?.today} />
        <Counter label="Trong tuần" value={counters?.week} />
        <Counter label="Trong tháng" value={counters?.month} />
        <Counter label="Tổng truy cập" value={counters?.total} />
      </ul>
    </>
  );
}

function Counter({ label, value }: { label: string; value?: number }) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-white/10 pb-0.5 last:border-0">
      <span className="text-white/75">{label}</span>
      <strong className="shrink-0 font-bold text-white">
        {value === undefined ? '…' : formatNumber(value)}
      </strong>
    </li>
  );
}
