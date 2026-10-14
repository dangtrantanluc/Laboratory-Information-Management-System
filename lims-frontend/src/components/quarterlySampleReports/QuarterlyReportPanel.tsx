/**
 * Báo cáo mẫu của MỘT phòng trong MỘT quý.
 *
 * Lab thấy nút Thêm mẫu / Nộp khi báo cáo đang ở tay mình (can_edit); Văn phòng thấy
 * Trả lại / Chốt / Mở khoá (can_review). Văn phòng không có nút sửa dòng — sai thì trả
 * lại để lab tự sửa, nhật ký mới truy được ai đổi số liệu.
 */
import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ListPlus, Lock, LockOpen, Pencil, Plus, Send, Trash2, Undo2 } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import * as api from '@/api/quarterlySampleReports';
import { BatchItemModal } from './BatchItemModal';
import { SampleItemModal } from './SampleItemModal';
import { ReasonModal, SubmitModal } from './ReportActionModals';

export const STATUS_TONE: Record<api.QuarterlyReportStatus, BadgeTone> = {
  draft: 'pending',
  submitted: 'info',
  returned: 'warning',
  locked: 'success',
};

type Dialog = 'submit' | 'return' | 'lock' | 'reopen' | null;

export function QuarterlyReportPanel({
  current,
  onChanged,
}: {
  current: api.CurrentQuarterlyReport;
  onChanged: () => void;
}) {
  const toast = useToast();
  const { report, year, quarter, department } = current;
  const period = api.periodLabel(year, quarter);
  const canEdit = current.can_edit;
  const canReview = !!report?.can_review;

  const [itemModal, setItemModal] = useState<{ report: api.QuarterlyReport; item?: api.QuarterlyReportItem } | null>(
    null,
  );
  const [batchReport, setBatchReport] = useState<api.QuarterlyReport | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<api.QuarterlyReportItem | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);

  // Cùng mã mẫu xuất hiện hai lần trong một báo cáo: có thể là hai đợt thật, có thể là
  // nhập trùng — không chặn, chỉ đánh dấu để người nhập tự kiểm.
  const dupCodes = useMemo(() => {
    const seen = new Map<string, number>();
    for (const it of report?.items ?? []) seen.set(it.sample_code, (seen.get(it.sample_code) ?? 0) + 1);
    return new Set([...seen].filter(([, n]) => n > 1).map(([c]) => c));
  }, [report]);

  async function run(fn: () => Promise<unknown>, success: string) {
    setBusy(true);
    try {
      await fn();
      toast.success(success);
      setDialog(null);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  async function openAdd(batch: boolean) {
    const open = (r: api.QuarterlyReport) => (batch ? setBatchReport(r) : setItemModal({ report: r }));
    if (report) return open(report);
    // Chưa lập báo cáo quý này — lập khi thêm dòng đầu tiên.
    setBusy(true);
    try {
      open(await api.ensureReport(year, quarter));
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  async function openSubmit() {
    if (!report) {
      // Nộp báo cáo rỗng ("không phát sinh mẫu") cũng cần có bản báo cáo.
      try {
        await api.ensureReport(year, quarter);
        onChanged();
      } catch (err) {
        return toast.error(describeError(err).title);
      }
    }
    setDialog('submit');
  }

  const columns: Column<api.QuarterlyReportItem>[] = [
    { key: 'stt', header: 'STT', align: 'center', render: (_r, i) => i + 1 },
    {
      key: 'code',
      header: 'Mã số mẫu',
      sortValue: (r) => r.sample_code,
      render: (r) => (
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
          {r.sample_code}
          {dupCodes.has(r.sample_code) && (
            <span title="Mã mẫu này xuất hiện nhiều lần trong báo cáo — kiểm tra có nhập trùng không">
              <AlertTriangle size={14} className="text-warning" />
            </span>
          )}
        </span>
      ),
    },
    { key: 'date', header: 'Ngày nhận', sortValue: (r) => r.received_date, render: (r) => formatDate(r.received_date) },
    { key: 'matrix', header: 'Loại mẫu', sortValue: (r) => r.matrix_label, render: (r) => r.matrix_label },
    { key: 'qty', header: 'Số lượng', align: 'center', sortValue: (r) => r.quantity, render: (r) => r.quantity },
    {
      key: 'criteria',
      header: 'Chỉ tiêu phân tích',
      render: (r) => <span className="block max-w-[360px] whitespace-normal">{r.criteria_text}</span>,
    },
    { key: 'note', header: 'Ghi chú', render: (r) => r.note ?? '—' },
    ...(canEdit && report
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (r: api.QuarterlyReportItem) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="secondary" onClick={() => setItemModal({ report, item: r })}>
                  <Pencil size={14} /> Sửa
                </Button>
                <Button size="icon" variant="ghost" aria-label={`Xóa mẫu ${r.sample_code}`} onClick={() => setDeleteTarget(r)}>
                  <Trash2 size={15} />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-base font-semibold text-ink">{department.name}</p>
            <p className="text-sm text-subink">
              Báo cáo mẫu phân tích {period}
              {report && (
                <>
                  {' · '}
                  <b className="text-ink">{report.item_count}</b> dòng, <b className="text-ink">{report.total_quantity}</b> mẫu
                </>
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={report ? STATUS_TONE[report.status] : 'neutral'} dot>
              {report?.status_label ?? 'Chưa bắt đầu'}
            </Badge>
            {canEdit && (
              <>
                <Button variant="secondary" onClick={() => openAdd(false)} disabled={busy && !dialog}>
                  <Plus size={16} /> Thêm mẫu
                </Button>
                <Button variant="secondary" onClick={() => openAdd(true)} disabled={busy && !dialog}>
                  <ListPlus size={16} /> Nhập nhiều mẫu
                </Button>
                <Button onClick={openSubmit}>
                  <Send size={16} /> {report?.status === 'returned' ? 'Nộp lại' : 'Nộp báo cáo'}
                </Button>
              </>
            )}
            {canReview && report?.status === 'submitted' && (
              <>
                <Button variant="secondary" onClick={() => setDialog('return')}>
                  <Undo2 size={16} /> Trả lại
                </Button>
                <Button onClick={() => setDialog('lock')}>
                  <Lock size={16} /> Chốt
                </Button>
              </>
            )}
            {canReview && report?.status === 'locked' && (
              <Button variant="secondary" onClick={() => setDialog('reopen')}>
                <LockOpen size={16} /> Mở khóa
              </Button>
            )}
          </div>
        </div>

        {report?.status === 'returned' && report.return_reason && (
          <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm">
            <p className="font-medium text-warning">
              <AlertTriangle size={14} className="mr-1 inline" />
              Văn phòng đã trả lại báo cáo
              {report.returned_at && ` — ${report.returned_by_name ?? ''}, ${formatDateTime(report.returned_at)}`}
            </p>
            <p className="mt-1 whitespace-pre-line text-ink">{report.return_reason}</p>
          </div>
        )}
        {report?.submitted_at && report.status !== 'returned' && (
          <p className="text-sm text-subink">
            Nộp bởi {report.submitted_by_name ?? '—'} lúc {formatDateTime(report.submitted_at)}
            {report.lab_note && <> — “{report.lab_note}”</>}
          </p>
        )}
        {report?.status === 'locked' && (
          <p className="flex items-center gap-1.5 text-sm text-success">
            <CheckCircle2 size={14} /> Đã chốt bởi {report.locked_by_name ?? '—'} lúc {formatDateTime(report.locked_at ?? undefined)}
          </p>
        )}
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={report?.items ?? []}
          rowKey={(r) => r.id}
          pageSize={50}
          empty={
            <EmptyState
              title="Chưa có mẫu nào"
              description={
                canEdit
                  ? `Bấm "Nhập nhiều mẫu" để nhập cả lô mẫu đã nhận trong ${period}, hoặc "Thêm mẫu" để nhập từng mẫu.`
                  : undefined
              }
            />
          }
        />
      </Card>

      {itemModal && (
        <SampleItemModal
          report={itemModal.report}
          item={itemModal.item}
          onClose={() => setItemModal(null)}
          onSaved={() => {
            toast.success(itemModal.item ? 'Đã cập nhật' : 'Đã thêm mẫu');
            setItemModal(null);
            onChanged();
          }}
        />
      )}
      {batchReport && (
        <BatchItemModal
          report={batchReport}
          onClose={() => setBatchReport(null)}
          onSaved={(n) => {
            toast.success(`Đã thêm ${n} mẫu`);
            setBatchReport(null);
            onChanged();
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => report && deleteTarget && run(() => api.deleteItem(report.id, deleteTarget.id), 'Đã xóa')}
        title="Xóa dòng mẫu"
        message={`Xóa mẫu "${deleteTarget?.sample_code}" khỏi báo cáo?`}
        confirmText="Xóa"
        loading={busy}
      />
      {dialog === 'submit' && report && (
        <SubmitModal
          itemCount={report.item_count}
          totalQuantity={report.total_quantity}
          period={period}
          loading={busy}
          onClose={() => setDialog(null)}
          onConfirm={(body) => run(() => api.submitReport(report.id, body), 'Đã nộp báo cáo cho Văn phòng')}
        />
      )}
      {dialog === 'return' && report && (
        <ReasonModal
          title="Trả lại báo cáo"
          description={`Báo cáo ${period} của ${department.name} sẽ về lại phòng lab để sửa và nộp lại.`}
          confirmText="Trả lại"
          loading={busy}
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run(() => api.returnReport(report.id, reason), 'Đã trả lại báo cáo')}
        />
      )}
      {dialog === 'reopen' && report && (
        <ReasonModal
          title="Mở khóa báo cáo đã chốt"
          description="Báo cáo sẽ về lại phòng lab để sửa. Số liệu đã xuất trước đó có thể không còn đúng."
          confirmText="Mở khóa"
          loading={busy}
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run(() => api.reopenReport(report.id, reason), 'Đã mở khóa báo cáo')}
        />
      )}
      <ConfirmDialog
        open={dialog === 'lock'}
        onClose={() => setDialog(null)}
        onConfirm={() => report && run(() => api.lockReport(report.id), 'Đã chốt báo cáo')}
        title="Chốt báo cáo"
        message={`Chốt báo cáo ${period} của ${department.name}? Sau khi chốt, phòng lab không sửa được nữa.`}
        confirmText="Chốt"
        tone="primary"
        loading={busy}
      />
    </div>
  );
}
