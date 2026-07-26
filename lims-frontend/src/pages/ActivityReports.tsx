import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarClock, Plus, CheckCircle2, Trash2, Eye } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime, formatMoney } from '@/lib/format';
import { ACTIVITY_REPORT_STATUS_LABELS } from '@/types';
import type { ActivityReport, ActivityReportStatus } from '@/types';
import { canSubmitActivityReport, canReviewActivityReports } from '@/lib/rbac';
import * as reportApi from '@/api/activityReport';

const STATUS_TONE: Record<ActivityReportStatus, BadgeTone> = {
  draft: 'muted',
  submitted: 'pending',
  reviewed: 'success',
};

function StatusBadge({ status }: { status: ActivityReportStatus }) {
  return <Badge tone={STATUS_TONE[status] ?? 'neutral'} dot>{ACTIVITY_REPORT_STATUS_LABELS[status]}</Badge>;
}

export function ActivityReports() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [period, setPeriod] = useState('');
  const [statusFilter, setStatusFilter] = useState<ActivityReportStatus | ''>('');
  const [viewId, setViewId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ActivityReport | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canReview = canReviewActivityReports(user);
  const canSubmit = canSubmitActivityReport(user);

  const { data, loading, reload } = useAsync(
    () => reportApi.listReports({ limit: 100, period: period || undefined, status: statusFilter || undefined }),
    [period, statusFilter],
  );

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await reportApi.deleteReport(deleteTarget.id);
      toast.success('Đã xóa báo cáo', 'Các dòng hoạt động đã nộp cũng được gỡ khỏi module.');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  function sumCounts(r: ActivityReport): number {
    const c = r.counts;
    if (!c) return 0;
    return c.teaching + c.projects + c.publications + c.contracts + c.activities;
  }

  const columns: Column<ActivityReport>[] = [
    { key: 'period', header: 'Kỳ', render: (r) => <span className="font-medium text-ink">{r.period_label}</span> },
    { key: 'reporter', header: 'Người nộp', render: (r) => r.reporter_name ?? '—' },
    { key: 'department', header: 'Phòng ban', render: (r) => r.department_name ?? '—' },
    { key: 'items', priority: 1, header: 'Số hoạt động', align: 'right', render: (r) => sumCounts(r) },
    { key: 'status', priority: 1, header: 'Trạng thái', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'submitted', header: 'Thời gian nộp', render: (r) => (r.submitted_at ? formatDateTime(r.submitted_at) : '—') },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="ghost" onClick={() => setViewId(r.id)}><Eye size={14} /></Button>
          {(canReview || r.reporter_user_id === user?.id) && (
            <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(r)}><Trash2 size={14} className="text-overdue" /></Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Báo cáo hoạt động tháng"
        description={canReview ? 'Tổng hợp báo cáo hoạt động do giảng viên / KTV / lãnh đạo nộp hàng tháng.' : 'Các báo cáo hoạt động bạn đã nộp.'}
        icon={<CalendarClock size={20} />}
        actions={canSubmit && <Button onClick={() => navigate('/activity-reports/new')}><Plus size={16} /> Nộp báo cáo</Button>}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <span className="text-sm text-subink">Kỳ:</span>
          <Input value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="07/2026" className="w-full sm:max-w-[140px]" />
          <span className="text-sm text-subink">Trạng thái:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ActivityReportStatus | '')}
            className="h-10 rounded-lg border border-hairline bg-surface px-3 text-sm text-ink"
          >
            <option value="">Tất cả</option>
            {(Object.keys(ACTIVITY_REPORT_STATUS_LABELS) as ActivityReportStatus[]).map((s) => (
              <option key={s} value={s}>{ACTIVITY_REPORT_STATUS_LABELS[s]}</option>
            ))}
          </select>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(r) => r.id} loading={loading} pageSize={15} onRowClick={(r) => setViewId(r.id)} />
      </Card>

      {viewId && (
        <ReportDetailModal
          reportId={viewId}
          canReview={canReview}
          onClose={() => setViewId(null)}
          onReviewed={() => { setViewId(null); reload(); }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa báo cáo"
        message="Xóa báo cáo này? Các dòng hoạt động đã đổ vào module (đề tài/bài báo/hợp đồng/giảng dạy/công tác khác) cũng sẽ bị gỡ."
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function money(v: string | null | undefined): string {
  return v ? formatMoney(v) : '—';
}

function ReportDetailModal({
  reportId,
  canReview,
  onClose,
  onReviewed,
}: {
  reportId: string;
  canReview: boolean;
  onClose: () => void;
  onReviewed: () => void;
}) {
  const toast = useToast();
  const [reviewing, setReviewing] = useState(false);
  const { data: r, loading } = useAsync(() => reportApi.getReport(reportId), [reportId]);

  async function review() {
    setReviewing(true);
    try {
      await reportApi.reviewReport(reportId);
      toast.success('Đã đánh dấu tổng hợp');
      onReviewed();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setReviewing(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={r ? `Báo cáo kỳ ${r.period_label}` : 'Chi tiết báo cáo'}
      description={r?.reporter_name ? `Người nộp: ${r.reporter_name}` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Đóng</Button>
          {canReview && r?.status === 'submitted' && (
            <Button onClick={review} loading={reviewing}><CheckCircle2 size={14} /> Đánh dấu đã tổng hợp</Button>
          )}
        </>
      }
    >
      {loading || !r ? (
        <div className="py-8 text-center text-sm text-subink">Đang tải…</div>
      ) : (
        <div className="flex flex-col gap-5">
          <DescList>
            <DescItem label="Kỳ báo cáo" value={r.period_label} />
            <DescItem label="Trạng thái" value={<StatusBadge status={r.status} />} />
            <DescItem label="Năm học" value={r.academic_year} />
            <DescItem label="Phòng ban" value={r.department_name} />
            <DescItem label="Thời gian nộp" value={r.submitted_at ? formatDateTime(r.submitted_at) : '—'} />
            <DescItem label="Đã tổng hợp bởi" value={r.reviewed_by_name ?? '—'} />
            {r.note && <DescItem full label="Ghi chú" value={<span className="whitespace-pre-wrap">{r.note}</span>} />}
          </DescList>

          <DetailSection title="Môn giảng dạy" rows={r.teaching}
            render={(t) => (<><div className="font-medium text-ink">{t.course_name}</div><div className="text-xs text-subink">LT/TH HK1: {t.hk1_theory_hours ?? 0}/{t.hk1_practice_hours ?? 0} · HK2: {t.hk2_theory_hours ?? 0}/{t.hk2_practice_hours ?? 0}</div></>)} />
          <DetailSection title="Đề tài NCKH" rows={r.projects}
            render={(p) => (<><div className="font-medium text-ink">{p.title}</div><div className="text-xs text-subink">{p.level ?? '—'} · KP: {money(p.budget_amount)}</div></>)} />
          <DetailSection title="Bài báo & Báo cáo KH" rows={r.publications}
            render={(p) => (<><div className="font-medium text-ink">{p.title}</div><div className="text-xs text-subink">{p.type} · {p.journal ?? '—'} · {p.year ?? '—'}{p.is_scie ? ' · SCIE' : ''}{p.is_scopus ? ' · Scopus' : ''}</div></>)} />
          <DetailSection title="Hợp đồng" rows={r.contracts}
            render={(c) => (<><div className="font-medium text-ink">{c.title}</div><div className="text-xs text-subink">{c.contract_type ?? '—'} · {money(c.value_amount)}</div></>)} />
          <DetailSection title="Công tác khác" rows={r.activities}
            render={(a) => (<><div className="font-medium text-ink">{a.content}</div><div className="text-xs text-subink">{a.kind}</div></>)} />
        </div>
      )}
    </Modal>
  );
}

function DetailSection<T>({ title, rows, render }: { title: string; rows?: T[]; render: (row: T) => React.ReactNode }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-ink">{title} <span className="text-subink">({rows.length})</span></div>
      <div className="flex flex-col divide-y divide-hairline rounded-lg border border-hairline">
        {rows.map((row, i) => <div key={i} className="p-3">{render(row)}</div>)}
      </div>
    </div>
  );
}
