import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FlaskConical,
  UserPlus,
  Send,
  FileDown,
  CheckCircle2,
  ClipboardCheck,
  AlertTriangle,
  History,
  Plus,
  Trash2,
  Paperclip,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { SampleStatusBadge, ApprovalBadge } from '@/components/ui/StatusBadge';
import { AttachmentPanel } from '@/components/ui/AttachmentPanel';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canAssignSample, canApproveResult, canEnterResult } from '@/lib/rbac';
import * as samplesApi from '@/api/samples';
import * as usersApi from '@/api/users';
import type { Assignment, SampleDetail, SampleResultItem } from '@/types';

const ASSIGNMENT_STATUS_LABEL: Record<string, string> = {
  assigned: 'Đã giao',
  in_progress: 'Đang làm',
  result_entered: 'Đã nhập KQ',
  approved: 'Đã duyệt',
};

// ── Kết quả: cầu nối giữa form thân thiện và result_data (object tự do) ──────
// Quy ước shape (tương thích PDF result-report đọc result_data.value/unit):
//   1 chỉ tiêu  → { value, unit, method }
//   nhiều chỉ tiêu → { indicators: [{ name, value, unit, method }] }
interface IndicatorRow {
  name: string;
  value: string;
  unit: string;
  method: string;
}

function emptyRow(): IndicatorRow {
  return { name: '', value: '', unit: '', method: '' };
}

/** Đọc result_data đã lưu thành danh sách dòng chỉ tiêu để hiển thị/sửa trên form. */
function rowsFromResultData(data: Record<string, unknown> | null | undefined): IndicatorRow[] {
  if (!data || typeof data !== 'object') return [emptyRow()];
  const indicators = (data as { indicators?: unknown }).indicators;
  if (Array.isArray(indicators)) {
    const rows = indicators
      .filter((it): it is Record<string, unknown> => !!it && typeof it === 'object')
      .map((it) => ({
        name: String(it.name ?? ''),
        value: String(it.value ?? ''),
        unit: String(it.unit ?? ''),
        method: String(it.method ?? ''),
      }));
    return rows.length ? rows : [emptyRow()];
  }
  // Shape 1 chỉ tiêu { value, unit, method }
  if ('value' in data || 'unit' in data || 'method' in data) {
    return [
      {
        name: '',
        value: String((data as Record<string, unknown>).value ?? ''),
        unit: String((data as Record<string, unknown>).unit ?? ''),
        method: String((data as Record<string, unknown>).method ?? ''),
      },
    ];
  }
  return [emptyRow()];
}

/** Build result_data từ các dòng chỉ tiêu (chỉ giữ field có giá trị). */
function resultDataFromRows(rows: IndicatorRow[]): Record<string, unknown> {
  const clean = rows.filter((r) => r.value.trim() !== '' || r.name.trim() !== '');
  if (clean.length === 1 && clean[0].name.trim() === '') {
    const r = clean[0];
    const obj: Record<string, unknown> = { value: r.value.trim() };
    if (r.unit.trim()) obj.unit = r.unit.trim();
    if (r.method.trim()) obj.method = r.method.trim();
    return obj;
  }
  return {
    indicators: clean.map((r) => {
      const ind: Record<string, unknown> = { name: r.name.trim(), value: r.value.trim() };
      if (r.unit.trim()) ind.unit = r.unit.trim();
      if (r.method.trim()) ind.method = r.method.trim();
      return ind;
    }),
  };
}

export function SampleDetailPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const sampleQ = useAsync(() => samplesApi.getSample(id), [id]);
  const custodyQ = useAsync(() => samplesApi.getCustodyChain(id), [id]);
  const resultsQ = useAsync(() => samplesApi.getSampleResults(id), [id]);

  const [assignOpen, setAssignOpen] = useState(false);
  const [handoverOpen, setHandoverOpen] = useState(false);
  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [overdueOpen, setOverdueOpen] = useState(false);
  const [resultModal, setResultModal] = useState<Assignment | null>(null);
  const [attachAssignment, setAttachAssignment] = useState<Assignment | null>(null);

  function reloadAll() {
    sampleQ.reload();
    custodyQ.reload();
    resultsQ.reload();
  }

  if (sampleQ.loading) return <LoadingState />;
  const s = sampleQ.data;
  if (!s)
    return (
      <Card>
        <EmptyState title="Không tìm thấy mẫu" />
      </Card>
    );

  const isAssignee = (a: Assignment) => a.assigned_to === user?.id;

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate(-1)}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Quay lại
      </button>

      <PageHeader
        title={s.sample_code}
        description={`${s.request_code} · ${s.department_name}`}
        icon={<FlaskConical size={20} />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <SampleStatusBadge status={s.status} />
            {canAssignSample(user) && s.status !== 'returned' && (
              <Button size="sm" variant="secondary" onClick={() => setAssignOpen(true)}>
                <UserPlus size={15} /> Phân công
              </Button>
            )}
            {s.status !== 'returned' && (
              <Button size="sm" variant="secondary" onClick={() => setHandoverOpen(true)}>
                <Send size={15} /> Chuyển giao
              </Button>
            )}
            {s.is_overdue && (
              <Button size="sm" variant="secondary" onClick={() => setOverdueOpen(true)}>
                <AlertTriangle size={15} /> Lý do trễ
              </Button>
            )}
            {canApproveResult(user) && s.can_finalize && (
              <Button size="sm" variant="success" onClick={() => setFinalizeOpen(true)}>
                <CheckCircle2 size={15} /> Chốt mẫu
              </Button>
            )}
            {(s.status === 'done' || s.status === 'returned') && (
              <Button
                size="sm"
                onClick={async () => {
                  try {
                    await samplesApi.exportResultReport(s.id, s.sample_code);
                  } catch (err) {
                    toast.error(describeError(err).title);
                  }
                }}
              >
                <FileDown size={15} /> Phiếu KQ (PDF)
              </Button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="Thông tin mẫu" />
          <CardBody className="flex flex-col gap-2.5 text-sm">
            <Row label="Mô tả" value={s.description} />
            <Row label="Khách hàng" value={s.customer_name ?? '—'} />
            <Row label="Ngày nhận" value={formatDateTime(s.received_at)} />
            <Row label="Hạn hoàn thành" value={formatDate(s.deadline_at)} />
            <Row
              label="Tình trạng"
              value={
                s.condition_status === 'acceptable'
                  ? 'Đạt'
                  : s.condition_status === 'not_acceptable'
                    ? `Không đạt${s.condition_note ? ` (${s.condition_note})` : ''}`
                    : '—'
              }
            />
            <Row label="Người giữ hiện tại" value={s.current_custodian?.name ?? '—'} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Phân công & Kết quả" subtitle="Tách bạch nhập kết quả và duyệt kết quả" />
          <CardBody className="p-0">
            {s.assignments.length === 0 ? (
              <EmptyState title="Chưa phân công" description="Trưởng nhóm phân công phần việc cho KTV." />
            ) : (
              <ul className="flex flex-col divide-y divide-hairline">
                {s.assignments.map((a) => {
                  const res = (resultsQ.data?.results ?? []).find((r) => r.assignment_id === a.id);
                  return (
                    <li key={a.id} className="flex flex-col gap-2 px-5 py-3.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-semibold text-ink">{a.part_name}</p>
                          <p className="text-xs text-subink">
                            KTV: {a.assigned_to_name} · giao bởi {a.assigned_by_name}
                          </p>
                        </div>
                        <Badge tone="neutral">{ASSIGNMENT_STATUS_LABEL[a.status] ?? a.status}</Badge>
                      </div>
                      <ResultRow
                        assignment={a}
                        result={res}
                        canEnter={canEnterResult(user) && isAssignee(a) && s.status !== 'returned'}
                        canApprove={canApproveResult(user)}
                        onEnter={() => setResultModal(a)}
                        onAttach={() => setAttachAssignment(a)}
                        onApprove={async (resultId) => {
                          try {
                            await samplesApi.approveResult(resultId);
                            toast.success('Đã duyệt kết quả');
                            reloadAll();
                          } catch (err) {
                            toast.error(describeError(err).title);
                          }
                        }}
                        onReturn={async (resultId, reason) => {
                          try {
                            await samplesApi.returnResult(resultId, reason);
                            toast.success('Đã trả lại để sửa');
                            reloadAll();
                          } catch (err) {
                            toast.error(describeError(err).title);
                          }
                        }}
                      />
                    </li>
                  );
                })}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Chứng từ đính kèm mẫu"
          subtitle="Phiếu gửi mẫu, biên bản tiếp nhận, ảnh tình trạng mẫu…"
        />
        <CardBody>
          <AttachmentPanel
            owner="sample"
            ownerId={s.id}
            canUpload={s.status !== 'returned'}
            uploadHint="PDF, PNG, JPG, XLSX — chứng từ gửi/tiếp nhận mẫu"
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Chuỗi hành trình mẫu (Chain of Custody)"
          subtitle="Lịch sử ai giữ mẫu, từ khi nào, lý do"
        />
        <CardBody>
          {custodyQ.loading ? (
            <LoadingState />
          ) : (custodyQ.data ?? []).length === 0 ? (
            <EmptyState icon={<History size={20} />} title="Chưa có dữ liệu hành trình" />
          ) : (
            <ol className="relative ml-3 flex flex-col gap-4 border-l-2 border-hairline pl-5">
              {(custodyQ.data ?? []).map((c, i) => (
                <li key={i} className="relative">
                  <span
                    className={`absolute -left-[27px] top-1 h-3 w-3 rounded-full ring-4 ring-white ${
                      c.is_current ? 'bg-blueberry' : 'bg-stem'
                    }`}
                  />
                  <p className="text-sm font-medium text-ink">
                    {c.custodian_name}
                    {c.is_current && <span className="ml-2 text-xs text-blueberry">(hiện tại)</span>}
                  </p>
                  <p className="text-xs text-subink">
                    {formatDateTime(c.from)} → {c.to ? formatDateTime(c.to) : 'nay'} · {c.reason}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </CardBody>
      </Card>

      {assignOpen && (
        <AssignModal
          sample={s}
          onClose={() => setAssignOpen(false)}
          onDone={() => {
            setAssignOpen(false);
            reloadAll();
            toast.success('Đã phân công');
          }}
        />
      )}
      {handoverOpen && (
        <HandoverModal
          sample={s}
          onClose={() => setHandoverOpen(false)}
          onDone={() => {
            setHandoverOpen(false);
            reloadAll();
            toast.success('Đã chuyển giao');
          }}
        />
      )}
      {resultModal && (
        <ResultModal
          assignment={resultModal}
          existing={(resultsQ.data?.results ?? []).find((r) => r.assignment_id === resultModal.id)}
          onClose={() => setResultModal(null)}
          onDone={() => {
            setResultModal(null);
            reloadAll();
            toast.success('Đã lưu kết quả');
          }}
        />
      )}
      {attachAssignment && (
        <ResultAttachmentsModal
          assignment={attachAssignment}
          canUpload={canEnterResult(user) && isAssignee(attachAssignment) && s.status !== 'returned'}
          onClose={() => setAttachAssignment(null)}
        />
      )}
      {finalizeOpen && (
        <SimpleReasonModal
          title="Chốt hoàn thành mẫu"
          label="Ghi chú (không bắt buộc)"
          required={false}
          confirmText="Chốt mẫu"
          onClose={() => setFinalizeOpen(false)}
          onSubmit={async (note) => {
            await samplesApi.finalizeSample(s.id, note || undefined);
            setFinalizeOpen(false);
            reloadAll();
            toast.success('Đã chốt mẫu');
          }}
        />
      )}
      {overdueOpen && (
        <SimpleReasonModal
          title="Nhập lý do trễ hạn"
          label="Lý do trễ"
          required
          confirmText="Lưu lý do"
          onClose={() => setOverdueOpen(false)}
          onSubmit={async (reason) => {
            await samplesApi.addOverdueReason(s.id, reason);
            setOverdueOpen(false);
            reloadAll();
            toast.success('Đã ghi lý do trễ');
          }}
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="shrink-0 text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function ResultRow({
  result,
  canEnter,
  canApprove,
  onEnter,
  onAttach,
  onApprove,
  onReturn,
}: {
  assignment: Assignment;
  result?: SampleResultItem;
  canEnter: boolean;
  canApprove: boolean;
  onEnter: () => void;
  onAttach: () => void;
  onApprove: (resultId: string) => void;
  onReturn: (resultId: string, reason: string) => void;
}) {
  const toast = useToast();
  // Lưu ý: SampleResultItem dùng assignment_id, không có result id; lấy result id cần gọi assignment results.
  // Để approve/return ta cần result id — dùng getAssignmentResult.
  async function withResultId(action: (rid: string) => void) {
    try {
      const r = await samplesApi.getAssignmentResult((result as SampleResultItem & { assignment_id: string }).assignment_id);
      if (!r) return toast.error('Chưa có kết quả');
      action(r.id);
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  return (
    <div className="rounded-lg bg-plate/60 px-3 py-2.5">
      {result ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0 text-sm">
            <div className="flex items-center gap-2">
              <ApprovalBadge status={result.approval_status} />
              {result.entered_by_name && (
                <span className="text-xs text-subink">Nhập: {result.entered_by_name}</span>
              )}
              {result.approved_by_name && (
                <span className="text-xs text-subink">· Duyệt: {result.approved_by_name}</span>
              )}
            </div>
            <div className="mt-1.5">
              {result.result_data ? (
                <ResultDataView data={result.result_data} />
              ) : (
                <span className="text-xs text-subink">Kết quả chưa công khai</span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 gap-1.5">
            <Button size="sm" variant="ghost" onClick={onAttach} title="Tệp đính kèm kết quả">
              <Paperclip size={14} /> Tệp
            </Button>
            {canEnter && result.approval_status !== 'approved' && (
              <Button size="sm" variant="ghost" onClick={onEnter}>
                Sửa
              </Button>
            )}
            {canApprove && result.approval_status === 'pending' && (
              <>
                <Button size="sm" variant="success" onClick={() => withResultId(onApprove)}>
                  <ClipboardCheck size={14} /> Duyệt
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    const reason = window.prompt('Lý do trả lại để sửa:');
                    if (reason) withResultId((rid) => onReturn(rid, reason));
                  }}
                >
                  Trả lại
                </Button>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 text-sm text-subink">
          <span>Chưa có kết quả</span>
          {canEnter && (
            <Button size="sm" onClick={onEnter}>
              Nhập kết quả
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function AssignModal({
  sample,
  onClose,
  onDone,
}: {
  sample: SampleDetail;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [partName, setPartName] = useState('');
  const [assignee, setAssignee] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(
    () => usersApi.listUsers({ department_id: sample.department_id, status: 'active', limit: 100 }),
    [sample.department_id],
  );

  async function submit() {
    if (!partName.trim()) return toast.error('Nhập tên phần việc');
    if (!assignee) return toast.error('Chọn KTV được giao');
    setSubmitting(true);
    try {
      await samplesApi.createAssignment(sample.id, partName.trim(), assignee);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Phân công phần việc"
      description="Chỉ giao cho KTV cùng phòng ban với mẫu."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Phân công
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Chỉ tiêu / phần việc" required>
          <Input value={partName} onChange={(e) => setPartName(e.target.value)} placeholder="vd: độ ẩm" />
        </Field>
        <Field label="KTV được giao" required>
          <Select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">— Chọn KTV —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function HandoverModal({
  sample,
  onClose,
  onDone,
}: {
  sample: SampleDetail;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [toUser, setToUser] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(
    () => usersApi.listUsers({ department_id: sample.department_id, status: 'active', limit: 100 }),
    [sample.department_id],
  );

  async function submit() {
    if (!toUser) return toast.error('Chọn người nhận');
    if (!reason.trim()) return toast.error('Nhập lý do chuyển giao');
    setSubmitting(true);
    try {
      await samplesApi.createHandover(sample.id, toUser, reason.trim());
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Chuyển giao mẫu"
      description="Ghi nhận chain of custody — không thể sửa/xóa sau khi tạo."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Chuyển giao
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Người nhận" required>
          <Select value={toUser} onChange={(e) => setToUser(e.target.value)}>
            <option value="">— Chọn người nhận —</option>
            {(users?.data ?? [])
              .filter((u) => u.id !== sample.current_custodian?.id)
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Lý do chuyển" required>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="vd: Chuyển sang đo phổ" />
        </Field>
      </div>
    </Modal>
  );
}

/** Hiển thị result_data dạng bảng chỉ tiêu (thay vì chuỗi JSON). */
function ResultDataView({ data }: { data: Record<string, unknown> }) {
  const rows = rowsFromResultData(data);
  const hasName = rows.some((r) => r.name.trim() !== '');
  const meaningful = rows.filter((r) => r.value.trim() !== '' || r.name.trim() !== '');
  if (meaningful.length === 0) {
    return (
      <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words text-xs text-ink">
        {JSON.stringify(data, null, 0)}
      </pre>
    );
  }
  return (
    <table className="text-xs">
      <tbody>
        {meaningful.map((r, i) => (
          <tr key={i} className="align-top">
            {hasName && <td className="pr-3 py-0.5 font-medium text-subink">{r.name || '—'}</td>}
            <td className="pr-2 py-0.5 font-semibold text-ink">
              {r.value}
              {r.unit ? <span className="ml-1 font-normal text-subink">{r.unit}</span> : null}
            </td>
            {r.method && <td className="py-0.5 text-subink">PP: {r.method}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ResultModal({
  assignment,
  existing,
  onClose,
  onDone,
}: {
  assignment: Assignment;
  existing?: SampleResultItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const isApproved = existing?.approval_status === 'approved';
  const [rows, setRows] = useState<IndicatorRow[]>(() => rowsFromResultData(existing?.result_data));
  const [advanced, setAdvanced] = useState(false);
  const [json, setJson] = useState(() =>
    JSON.stringify(resultDataFromRows(rowsFromResultData(existing?.result_data)), null, 2),
  );
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function updateRow(idx: number, patch: Partial<IndicatorRow>) {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }
  function removeRow(idx: number) {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));
  }

  /** Khi bật JSON nâng cao: nạp JSON từ form. Khi tắt: cố gắng parse JSON về form. */
  function toggleAdvanced() {
    if (!advanced) {
      setJson(JSON.stringify(resultDataFromRows(rows), null, 2));
      setAdvanced(true);
    } else {
      try {
        setRows(rowsFromResultData(JSON.parse(json)));
        setAdvanced(false);
      } catch {
        toast.error('JSON không hợp lệ — sửa lại trước khi quay về dạng form');
      }
    }
  }

  function buildResultData(): Record<string, unknown> | null {
    if (advanced) {
      try {
        const parsed = JSON.parse(json);
        if (!parsed || typeof parsed !== 'object' || Object.keys(parsed).length === 0) {
          toast.error('Kết quả không được rỗng');
          return null;
        }
        return parsed as Record<string, unknown>;
      } catch {
        toast.error('Dữ liệu kết quả phải là JSON hợp lệ');
        return null;
      }
    }
    const hasValue = rows.some((r) => r.value.trim() !== '');
    if (!hasValue) {
      toast.error('Nhập ít nhất một giá trị kết quả');
      return null;
    }
    return resultDataFromRows(rows);
  }

  async function submit() {
    const resultData = buildResultData();
    if (!resultData) return;
    if (isApproved && !reason.trim()) return toast.error('Cần nhập lý do khi sửa kết quả đã duyệt');
    setSubmitting(true);
    try {
      if (isApproved) {
        // sửa kết quả đã duyệt = revise (cần result id)
        const r = await samplesApi.getAssignmentResult(assignment.id);
        if (!r) throw new Error('Không tìm thấy kết quả');
        await samplesApi.reviseResult(r.id, resultData, reason.trim());
      } else {
        await samplesApi.enterResult(assignment.id, resultData);
      }
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={isApproved ? `Sửa kết quả (bản mới) — ${assignment.part_name}` : `Nhập kết quả — ${assignment.part_name}`}
      description="Nhập từng chỉ tiêu: giá trị, đơn vị, phương pháp. Bật JSON nâng cao nếu cần cấu trúc tùy chỉnh."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu kết quả
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Chỉ tiêu kết quả</span>
          <button
            type="button"
            onClick={toggleAdvanced}
            className="text-xs font-medium text-blueberry hover:underline"
          >
            {advanced ? 'Về dạng form' : 'JSON nâng cao'}
          </button>
        </div>

        {advanced ? (
          <Field label="Dữ liệu kết quả (JSON)" required>
            <Textarea
              value={json}
              onChange={(e) => setJson(e.target.value)}
              className="min-h-[180px] font-mono text-xs"
            />
          </Field>
        ) : (
          <div className="flex flex-col gap-3">
            {rows.map((row, idx) => (
              <div key={idx} className="rounded-lg border border-hairline bg-plate/40 p-3">
                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  <Field label="Chỉ tiêu">
                    <Input
                      value={row.name}
                      onChange={(e) => updateRow(idx, { name: e.target.value })}
                      placeholder="vd: pH (để trống nếu chỉ 1 chỉ tiêu)"
                    />
                  </Field>
                  <Field label="Giá trị" required>
                    <Input
                      value={row.value}
                      onChange={(e) => updateRow(idx, { value: e.target.value })}
                      placeholder="vd: 7.2"
                    />
                  </Field>
                  <Field label="Đơn vị">
                    <Input
                      value={row.unit}
                      onChange={(e) => updateRow(idx, { unit: e.target.value })}
                      placeholder="vd: mg/L"
                    />
                  </Field>
                  <Field label="Phương pháp">
                    <Input
                      value={row.method}
                      onChange={(e) => updateRow(idx, { method: e.target.value })}
                      placeholder="vd: TCVN 6492:2011"
                    />
                  </Field>
                </div>
                {rows.length > 1 && (
                  <div className="mt-2 flex justify-end">
                    <Button size="sm" variant="ghost" onClick={() => removeRow(idx)}>
                      <Trash2 size={14} /> Xóa chỉ tiêu
                    </Button>
                  </div>
                )}
              </div>
            ))}
            <Button size="sm" variant="secondary" onClick={addRow} className="w-fit">
              <Plus size={14} /> Thêm chỉ tiêu
            </Button>
          </div>
        )}

        {isApproved && (
          <Field label="Lý do sửa (bắt buộc)" required>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="vd: Phát hiện sai số hiệu chuẩn" />
          </Field>
        )}
      </div>
    </Modal>
  );
}

/** Modal đính kèm raw data / chứng từ cho 1 kết quả (theo result id). */
function ResultAttachmentsModal({
  assignment,
  canUpload,
  onClose,
}: {
  assignment: Assignment;
  canUpload: boolean;
  onClose: () => void;
}) {
  const resultQ = useAsync(() => samplesApi.getAssignmentResult(assignment.id), [assignment.id]);

  return (
    <Modal
      open
      onClose={onClose}
      title={`Tệp kết quả — ${assignment.part_name}`}
      description="Dữ liệu thô, phổ đồ, ảnh chụp… gắn theo bản ghi kết quả."
      footer={
        <Button variant="secondary" onClick={onClose}>
          Đóng
        </Button>
      }
    >
      {resultQ.loading ? (
        <LoadingState />
      ) : !resultQ.data ? (
        <EmptyState
          title="Chưa có kết quả"
          description="Cần nhập kết quả trước khi đính kèm tệp."
        />
      ) : (
        <AttachmentPanel
          owner="result"
          ownerId={resultQ.data.id}
          canUpload={canUpload}
          uploadHint="PDF, PNG, JPG, XLSX — dữ liệu thô / phổ đồ kết quả"
        />
      )}
    </Modal>
  );
}

function SimpleReasonModal({
  title,
  label,
  required,
  confirmText,
  onClose,
  onSubmit,
}: {
  title: string;
  label: string;
  required: boolean;
  confirmText: string;
  onClose: () => void;
  onSubmit: (text: string) => Promise<void>;
}) {
  const toast = useToast();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (required && !text.trim()) return toast.error('Vui lòng nhập nội dung');
    setSubmitting(true);
    try {
      await onSubmit(text.trim());
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            {confirmText}
          </Button>
        </>
      }
    >
      <Field label={label} required={required}>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
    </Modal>
  );
}
