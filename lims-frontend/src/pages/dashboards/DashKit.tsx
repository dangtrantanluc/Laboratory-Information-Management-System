import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, RefreshCw } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/cn';

/** Khung chung mọi dashboard: lời chào + phụ đề theo vai trò + nút làm mới. */
export function DashLayout({
  subtitle,
  onRefresh,
  loading,
  extraActions,
  children,
}: {
  subtitle: string;
  onRefresh: () => void;
  loading?: boolean;
  extraActions?: ReactNode;
  children: ReactNode;
}) {
  const { user } = useAuth();
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`Xin chào, ${user?.full_name ?? ''}`}
        description={subtitle}
        icon={<LayoutDashboard size={20} />}
        actions={
          <div className="flex items-center gap-2">
            {extraActions}
            <Button variant="secondary" size="sm" onClick={onRefresh} loading={loading}>
              <RefreshCw size={15} /> Làm mới
            </Button>
          </div>
        }
      />
      {children}
    </div>
  );
}

export type KpiTone = 'info' | 'pending' | 'overdue' | 'success' | 'warning' | 'neutral';

const TONE_ICON: Record<KpiTone, string> = {
  info: 'bg-berry/10 text-berry',
  pending: 'bg-pending/10 text-pending',
  overdue: 'bg-overdue/10 text-overdue',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  neutral: 'bg-stem/10 text-stem',
};

export interface KpiSpec {
  icon: ReactNode;
  tone: KpiTone;
  label: string;
  value: number | string;
  hint?: string;
  to?: string;
}

/** Thẻ KPI: số lớn + nhãn + icon tone. Bấm để đi tới trang lọc sẵn. */
export function KpiTile({ icon, tone, label, value, hint, to }: KpiSpec) {
  const navigate = useNavigate();
  const clickable = !!to;
  return (
    <Card className={cn('h-full', clickable && 'cursor-pointer transition-shadow hover:shadow-pop')}>
      <button
        type="button"
        onClick={to ? () => navigate(to) : undefined}
        disabled={!clickable}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:cursor-default sm:gap-4 sm:px-5 sm:py-4"
      >
        <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl sm:h-11 sm:w-11', TONE_ICON[tone])}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-xl font-bold leading-tight text-ink sm:text-2xl">{value}</p>
          <p className="truncate text-xs text-subink">{label}</p>
          {hint && <p className="truncate text-[11px] text-stem">{hint}</p>}
        </div>
      </button>
    </Card>
  );
}

export function KpiGrid({ items }: { items: KpiSpec[] }) {
  if (items.length === 0) return null;
  return (
    <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 sm:gap-4 lg:grid-cols-4 3xl:grid-cols-5">
      {items.map((k, i) => (
        // "Nảy mầm" lần lượt từng thẻ (stagger 45ms) — cảm giác sinh trưởng khi tải trang
        <div key={i} className="animate-sprout" style={{ animationDelay: `${i * 45}ms` }}>
          <KpiTile {...k} />
        </div>
      ))}
    </div>
  );
}

export interface QuickAction {
  icon: ReactNode;
  label: string;
  to: string;
}

/** Hàng nút hành động nhanh — đưa người dùng thẳng tới việc hay làm nhất. */
export function QuickActions({ actions }: { actions: QuickAction[] }) {
  const navigate = useNavigate();
  if (actions.length === 0) return null;
  return (
    <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 no-scrollbar sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
      {actions.map((a) => (
        <button
          key={a.label}
          onClick={() => navigate(a.to)}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-hairline bg-surface px-3.5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-plate hover:text-blueberry sm:py-2"
        >
          {a.icon}
          {a.label}
        </button>
      ))}
    </div>
  );
}

/** Danh sách "cần xử lý": mỗi dòng số + nhãn, bấm đi tới trang lọc. */
export function AlertList({ title, rows }: { title: string; rows: { label: string; value: number; tone?: KpiTone; to?: string }[] }) {
  const navigate = useNavigate();
  return (
    <Card className="h-full">
      <div className="border-b border-hairline px-5 py-3">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
      </div>
      <CardBody className="flex flex-col divide-y divide-hairline p-0">
        {rows.map((r) => (
          <button
            key={r.label}
            onClick={r.to ? () => navigate(r.to!) : undefined}
            disabled={!r.to}
            className="flex items-center justify-between gap-3 px-5 py-3 text-left transition-colors enabled:hover:bg-plate disabled:cursor-default"
          >
            <span className="text-sm text-ink">{r.label}</span>
            <span
              className={cn(
                'min-w-[28px] rounded-full px-2 py-0.5 text-center text-sm font-bold',
                r.value === 0
                  ? 'bg-stem/10 text-stem'
                  : r.tone === 'overdue'
                    ? 'bg-overdue/10 text-overdue'
                    : r.tone === 'warning'
                      ? 'bg-warning/10 text-warning'
                      : r.tone === 'success'
                        ? 'bg-success/10 text-success'
                        : 'bg-pending/10 text-pending',
              )}
            >
              {r.value}
            </span>
          </button>
        ))}
      </CardBody>
    </Card>
  );
}
