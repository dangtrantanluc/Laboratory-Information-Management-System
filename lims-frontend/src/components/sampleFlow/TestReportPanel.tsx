/**
 * Khối "Kết quả thử nghiệm" trong chi tiết phiếu nhận mẫu (m46) — BM 7.8/01/RIBE.
 *
 * Đây là bước PHÁT HÀNH: chứng từ trả cho khách, tải tệp lên chứ không sinh từ dữ liệu.
 * Trước m46, "Đã trả kết quả" chỉ là một giá trị trạng thái trên phiếu — không tệp,
 * không số hiệu, không người ký, nên khách khiếu nại thì không có gì đối chiếu.
 *
 * Vòng đời: Nháp → Đã phát hành → Đã gửi khách, cộng Thu hồi. Nút bấm dựng từ
 * `next_statuses` backend trả về, không đoán theo `status` — một nguồn sự thật.
 */
import { useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, FileText, FileUp, Pencil, Send, ShieldX, Trash2, Upload,
} from 'lucide-react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { EmptyState, Spinner } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { useAsync } from '@/lib/useAsync';
import { cn } from '@/lib/cn';
import {
  DELIVERY_METHOD_LABELS,
  type DeliveryMethod,
  type SampleIntake,
  type TestReport,
} from '@/types';
import * as api from '@/api/testReports';

/** Khớp allowlist riêng của module ở backend (test_report_service). */
const ACCEPT = '.pdf,.doc,.docx';

const TONE: Record<TestReport['status'], BadgeTone> = {
  draft: 'neutral',
  issued: 'success',
  delivered: 'info',
  revoked: 'overdue',
};

function formatBytes(size: number | null): string {
  if (size == null) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** Ngày hôm nay dạng yyyy-mm-dd cho <input type="date"> — theo giờ địa phương. */
function today(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function TestReportPanel({
  intake,
  canManage,
  onChanged,
}: {
  intake: SampleIntake;
  /** canManageTestReports — reception / leader / admin. */
  canManage: boolean;
  /** Gọi sau khi có thay đổi để phiếu cha tải lại (badge KQ, chặn completed). */
  onChanged: () => void;
}) {
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => api.listTestReports(intake.id), [intake.id]);
  const [creating, setCreating] = useState(false);
  const [deliverFor, setDeliverFor] = useState<TestReport | null>(null);
  const [reviseFor, setReviseFor] = useState<TestReport | null>(null);
  const [revokeFor, setRevokeFor] = useState<TestReport | null>(null);
  const [deleteFor, setDeleteFor] = useState<TestReport | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const reports = data ?? [];

  function refresh() {
    reload();
    onChanged();
  }

  // BR-09 / BR-10 — CẢNH BÁO, không chặn. Trả kết quả từng phần là việc có thật (chỉ
  // tiêu gửi thầu phụ, ký hiệu (**) trên chính biểu mẫu), và có khách được cho nợ.
  const warnings = useMemo(() => {
    const out: string[] = [];
    if (intake.payment_status && intake.payment_status !== 'paid'
        && intake.payment_status !== 'waived') {
      out.push('Khách chưa thanh toán đủ.');
    }
    const pending = (intake.dispatches ?? []).filter((d) => d.status !== 'done').length;
    if (pending > 0) out.push(`Còn ${pending} chỉ tiêu chưa hoàn thành ở phòng lab.`);
    return out;
  }, [intake.payment_status, intake.dispatches]);

  async function act(report: TestReport, fn: () => Promise<unknown>, okMsg: string) {
    setBusyId(report.id);
    try {
      await fn();
      toast.success(okMsg);
      refresh();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="rounded-lg border border-hairline">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-3 py-2">
        <div className="flex items-center gap-2">
          <FileText size={15} className="text-subink" />
          <span className="text-sm font-semibold text-ink">Kết quả thử nghiệm</span>
          <span className="text-xs text-subink">BM 7.8/01</span>
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Upload size={14} /> Tải phiếu kết quả lên
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3 p-3">
        {warnings.length > 0 && reports.length === 0 && (
          <div className="flex items-start gap-2 rounded-md bg-warning/10 px-3 py-2 text-xs text-ink">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warning" />
            <div>
              <div className="font-medium">Lưu ý trước khi phát hành</div>
              <ul className="mt-0.5 list-disc pl-4 text-subink">
                {warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-6"><Spinner /></div>
        ) : reports.length === 0 ? (
          <EmptyState
            icon={<FileText size={20} />}
            title="Chưa có phiếu kết quả"
            description={
              canManage
                ? 'Soạn phiếu BM 7.8/01 trong Word, xuất PDF rồi tải lên đây. Phiếu chỉ được đánh dấu "Đã trả kết quả" sau khi có ít nhất một bản đã phát hành.'
                : 'Phòng nhận mẫu chưa phát hành phiếu kết quả cho phiếu này.'
            }
          />
        ) : (
          reports.map((r) => (
            <ReportRow
              key={r.id}
              report={r}
              canManage={canManage}
              busy={busyId === r.id}
              onOpenFile={(fileId) =>
                api.openTestReportFile(r.id, fileId).catch((e) =>
                  toast.error(describeError(e).title))
              }
              onUploaded={refresh}
              onIssue={() => act(r, () => api.issueTestReport(r.id), `Đã phát hành ${r.report_no}`)}
              onDeliver={() => setDeliverFor(r)}
              onRevise={() => setReviseFor(r)}
              onRevoke={() => setRevokeFor(r)}
              onDelete={() => setDeleteFor(r)}
            />
          ))
        )}
      </div>

      {creating && (
        <CreateReportModal
          intake={intake}
          onClose={() => setCreating(false)}
          onDone={() => { setCreating(false); refresh(); }}
        />
      )}
      {deliverFor && (
        <DeliverModal
          report={deliverFor}
          intake={intake}
          onClose={() => setDeliverFor(null)}
          onDone={() => { setDeliverFor(null); refresh(); }}
        />
      )}
      {reviseFor && (
        <ReasonModal
          title={`Tạo bản sửa đổi cho ${reviseFor.report_no}`}
          description="Bản cũ chuyển sang 'Đã thu hồi' và được giữ nguyên — khách đang cầm nó trên tay. Bản mới là bản nháp, cần tải tệp đã sửa lên rồi phát hành lại."
          label="Lý do sửa đổi"
          confirmText="Tạo bản sửa đổi"
          onClose={() => setReviseFor(null)}
          onSubmit={async (reason) => {
            const created = await api.reviseTestReport(reviseFor.id, reason);
            toast.success(`Đã tạo bản sửa đổi ${created.report_no}`, 'Tải tệp đã sửa lên rồi phát hành.');
            setReviseFor(null);
            refresh();
          }}
        />
      )}
      {revokeFor && (
        <ReasonModal
          title={`Thu hồi ${revokeFor.report_no}`}
          description="Mọi người đã từng tải tệp này về sẽ nhận được thông báo — họ có thể đã gửi bản sai đi rồi."
          label="Lý do thu hồi"
          confirmText="Thu hồi"
          danger
          onClose={() => setRevokeFor(null)}
          onSubmit={async (reason) => {
            await api.revokeTestReport(revokeFor.id, reason);
            toast.success(`Đã thu hồi ${revokeFor.report_no}`);
            setRevokeFor(null);
            refresh();
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteFor}
        onClose={() => setDeleteFor(null)}
        title="Xóa bản nháp?"
        message={`Xóa bản nháp ${deleteFor?.report_no ?? ''} cùng các tệp đã tải lên. Số hiệu được trả lại để dùng cho lần lập sau.`}
        confirmText="Xóa"
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await api.deleteTestReport(deleteFor.id);
            toast.success('Đã xóa bản nháp');
            setDeleteFor(null);
            refresh();
          } catch (err) {
            toast.error(describeError(err).title);
          }
        }}
      />
    </div>
  );
}

// ═══════════════════════════ Một dòng chứng từ ═══════════════════════════

function ReportRow({
  report, canManage, busy, onOpenFile, onUploaded,
  onIssue, onDeliver, onRevise, onRevoke, onDelete,
}: {
  report: TestReport;
  canManage: boolean;
  busy: boolean;
  onOpenFile: (fileId: string) => void;
  onUploaded: () => void;
  onIssue: () => void;
  onDeliver: () => void;
  onRevise: () => void;
  onRevoke: () => void;
  onDelete: () => void;
}) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const can = (s: TestReport['status']) => report.next_statuses.includes(s);
  const isDraft = report.status === 'draft';

  async function upload(f: File | null) {
    if (!f) return;
    setUploading(true);
    try {
      await api.uploadTestReportFile(report.id, f);
      toast.success('Đã tải tệp lên');
      onUploaded();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  return (
    <div className={cn(
      'rounded-md border border-hairline p-3',
      report.status === 'revoked' && 'opacity-70',
    )}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn(
          'font-mono text-sm font-semibold text-ink',
          report.status === 'revoked' && 'line-through',
        )}>
          {report.report_no}
        </span>
        {report.version > 1 && <Badge tone="muted">Bản sửa đổi {report.version - 1}</Badge>}
        <Badge tone={TONE[report.status]}>{report.status_label}</Badge>
        {typeof report.days_late === 'number' && report.days_late > 0 && (
          <Badge tone="overdue">Trả trễ {report.days_late} ngày</Badge>
        )}
      </div>

      <div className="mt-1.5 grid grid-cols-1 gap-x-4 gap-y-0.5 text-xs text-subink sm:grid-cols-2">
        {report.issued_at && (
          <div>Phát hành: <span className="text-ink">{formatDate(report.issued_at)}</span>
            {report.issued_by_name ? ` · ${report.issued_by_name}` : ''}</div>
        )}
        {report.delivered_at && (
          <div>Gửi khách: <span className="text-ink">{formatDateTime(report.delivered_at)}</span>
            {report.delivery_method_label ? ` · ${report.delivery_method_label}` : ''}
            {report.delivered_to ? ` → ${report.delivered_to}` : ''}</div>
        )}
        {report.supersedes_report_no && (
          <div>Thay cho: <span className="font-mono text-ink">{report.supersedes_report_no}</span></div>
        )}
        {report.title && <div className="sm:col-span-2">{report.title}</div>}
      </div>

      {report.revoked_reason && (
        <div className="mt-1.5 rounded bg-overdue/10 px-2 py-1 text-xs text-ink">
          <b>Lý do thu hồi:</b> {report.revoked_reason}
        </div>
      )}
      {report.revision_reason && (
        <div className="mt-1.5 text-xs text-subink">
          <b>Lý do sửa đổi:</b> {report.revision_reason}
        </div>
      )}

      {/* Tệp */}
      <div className="mt-2 flex flex-col gap-1">
        {report.files.length === 0 ? (
          <div className="text-xs italic text-subink">Chưa có tệp — phát hành sẽ bị từ chối.</div>
        ) : (
          report.files.map((f) => (
            <div key={f.id} className="flex flex-wrap items-center gap-2 text-xs">
              <button
                type="button"
                className="flex items-center gap-1 text-blueberry hover:underline"
                onClick={() => onOpenFile(f.id)}
              >
                <FileText size={13} /> {f.file_name}
              </button>
              <span className="text-subink">{formatBytes(f.size)}</span>
              {canManage && isDraft && (
                <button
                  type="button"
                  className="text-subink hover:text-overdue"
                  title="Gỡ tệp"
                  onClick={async () => {
                    try {
                      await api.deleteTestReportFile(report.id, f.id);
                      toast.success('Đã gỡ tệp');
                      onUploaded();
                    } catch (err) {
                      toast.error(describeError(err).title);
                    }
                  }}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {canManage && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {isDraft && (
            <>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => upload(e.target.files?.[0] ?? null)}
              />
              <Button
                variant="secondary" size="sm" loading={uploading}
                onClick={() => fileInput.current?.click()}
              >
                <FileUp size={14} /> Thêm tệp
              </Button>
            </>
          )}
          {can('issued') && (
            <Button size="sm" loading={busy} disabled={report.files.length === 0} onClick={onIssue}>
              <Send size={14} /> Phát hành
            </Button>
          )}
          {can('delivered') && (
            <Button variant="secondary" size="sm" onClick={onDeliver}>
              <Send size={14} /> Ghi nhận đã gửi khách
            </Button>
          )}
          {(report.status === 'issued' || report.status === 'delivered') && (
            <Button variant="secondary" size="sm" onClick={onRevise}>
              <Pencil size={14} /> Tạo bản sửa đổi
            </Button>
          )}
          {can('revoked') && (
            <Button variant="secondary" size="sm" onClick={onRevoke}>
              <ShieldX size={14} /> Thu hồi
            </Button>
          )}
          {isDraft && (
            <Button variant="secondary" size="sm" onClick={onDelete}>
              <Trash2 size={14} /> Xóa
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════ Modal: tải lên ═══════════════════════════

function CreateReportModal({
  intake, onClose, onDone,
}: {
  intake: SampleIntake;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  // Điền sẵn số hiệu bằng mã phiếu — đúng thứ in ở ô "Mã KH/Customer code" trên
  // biểu mẫu. Backend tự thêm hậu tố nếu mã đã có phiếu kết quả.
  const [reportNo, setReportNo] = useState(intake.code);
  const [issuedAt, setIssuedAt] = useState(today());
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!file) {
      toast.error('Chọn tệp phiếu kết quả trước');
      return;
    }
    setBusy(true);
    try {
      // Hai lệnh gọi cho một thao tác của người dùng: lập bản ghi rồi gắn tệp. Bản
      // nháp không có tệp vẫn hợp lệ (phát hành mới đòi), nên hỏng ở bước hai không
      // để lại rác — người dùng bấm "Thêm tệp" trên chính dòng đó là xong.
      const created = await api.createTestReport(intake.id, {
        report_no: reportNo.trim() || null,
        issued_at: issuedAt || null,
        title: title.trim() || null,
      });
      await api.uploadTestReportFile(created.id, file);
      toast.success(
        `Đã tạo bản nháp ${created.report_no}`,
        'Kiểm tra lại tệp rồi bấm "Phát hành".',
      );
      onDone();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Tải phiếu kết quả lên"
      description={`Phiếu ${intake.code} · ${intake.customer_name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button loading={busy} onClick={submit}>Lưu bản nháp</Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <Field label="Tệp phiếu kết quả" required hint="PDF hoặc Word (.doc/.docx)">
          <input
            type="file"
            accept={ACCEPT}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Số hiệu phiếu" hint="Mặc định theo mã phiếu nhận mẫu">
            <Input value={reportNo} onChange={(e) => setReportNo(e.target.value)} />
          </Field>
          <Field label="Ngày trả kết quả">
            <Input type="date" value={issuedAt} onChange={(e) => setIssuedAt(e.target.value)} />
          </Field>
        </div>
        <Field label="Ghi chú trên phiếu" hint="Tùy chọn — ví dụ: phiếu tách theo hộ">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <p className="text-xs text-subink">
          Bản tải lên là bản <b>nháp</b>. Kiểm tra xong bấm “Phát hành” — từ lúc đó tệp
          bị khóa, muốn sửa phải tạo bản sửa đổi.
        </p>
      </div>
    </Modal>
  );
}

// ═══════════════════════════ Modal: ghi nhận đã gửi ═══════════════════════════

function DeliverModal({
  report, intake, onClose, onDone,
}: {
  report: TestReport;
  intake: SampleIntake;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  // Điền sẵn từ ô "Hình thức trả kết quả" khách đã chọn lúc nhận mẫu (BM 7.1.01).
  const preset = (['direct', 'mail', 'email'] as DeliveryMethod[])
    .includes(intake.return_method as DeliveryMethod)
    ? (intake.return_method as DeliveryMethod)
    : 'direct';
  const [method, setMethod] = useState<DeliveryMethod>(preset);
  const [to, setTo] = useState(intake.contact_person ?? '');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  return (
    <Modal
      open
      onClose={onClose}
      title={`Ghi nhận đã gửi ${report.report_no}`}
      description="Đây là mốc “trả kết quả” thật của phiếu."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.deliverTestReport(report.id, {
                  delivery_method: method,
                  delivered_to: to.trim() || null,
                  delivery_note: note.trim() || null,
                });
                toast.success('Đã ghi nhận gửi khách');
                onDone();
              } catch (err) {
                const e = describeError(err);
                toast.error(e.title, e.description);
              } finally {
                setBusy(false);
              }
            }}
          >
            Lưu
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <Field label="Hình thức" required>
          <Select value={method} onChange={(e) => setMethod(e.target.value as DeliveryMethod)}>
            {(Object.keys(DELIVERY_METHOD_LABELS) as DeliveryMethod[]).map((m) => (
              <option key={m} value={m}>{DELIVERY_METHOD_LABELS[m]}</option>
            ))}
          </Select>
        </Field>
        <Field label="Người nhận" hint="Điền sẵn từ người liên hệ trên phiếu — sửa được">
          <Input value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
        <Field label="Ghi chú">
          <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

// ═══════════════════════════ Modal: nhập lý do ═══════════════════════════

function ReasonModal({
  title, description, label, confirmText, danger, onClose, onSubmit,
}: {
  title: string;
  description: string;
  label: string;
  confirmText: string;
  danger?: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const toast = useToast();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button
            loading={busy}
            variant={danger ? 'danger' : 'primary'}
            onClick={async () => {
              if (!reason.trim()) {
                toast.error('Phải nêu lý do — hồ sơ cần giải trình được');
                return;
              }
              setBusy(true);
              try {
                await onSubmit(reason.trim());
              } catch (err) {
                const e = describeError(err);
                toast.error(e.title, e.description);
              } finally {
                setBusy(false);
              }
            }}
          >
            {confirmText}
          </Button>
        </>
      }
    >
      <Field label={label} required>
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
    </Modal>
  );
}
