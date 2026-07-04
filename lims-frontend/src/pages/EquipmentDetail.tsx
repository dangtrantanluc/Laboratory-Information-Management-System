import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Wrench,
  Download,
  Plus,
  Pencil,
  Paperclip,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import {
  EquipmentStatusBadge,
  CalibrationStatusBadge,
} from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canWriteEquipmentDept } from '@/lib/rbac';
import {
  EQUIPMENT_STATUS_LABELS,
  CALIBRATION_CYCLE_UNIT_LABELS,
  CALIBRATION_RESULT_LABELS,
  type CalibrationCycleUnit,
  type CalibrationResult,
  type EquipmentDetail as EquipmentDetailType,
  type EquipmentStatus,
} from '@/types';
import * as equipApi from '@/api/equipment';
import * as usersApi from '@/api/users';

const MAX_FILE_MB = 20;
const ATTACH_ACCEPT = '.pdf,.docx,.xlsx,.png,.jpg,.jpeg';
const CERT_ACCEPT = '.pdf,.png,.jpg,.jpeg';

function formatSize(bytes?: number): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function cycleLabel(e: EquipmentDetailType): string {
  if (!e.calibration_cycle_value || !e.calibration_cycle_unit) return 'Không diện hiệu chuẩn';
  return `${e.calibration_cycle_value} ${CALIBRATION_CYCLE_UNIT_LABELS[e.calibration_cycle_unit]}`;
}

export function EquipmentDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const eqQ = useAsync(() => equipApi.getEquipment(id), [id]);
  const calQ = useAsync(() => equipApi.listCalibrations(id, { limit: 100 }), [id]);

  const [editOpen, setEditOpen] = useState(false);
  const [calibrateOpen, setCalibrateOpen] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);

  if (eqQ.loading) return <LoadingState />;
  const eq = eqQ.data;
  if (!eq)
    return (
      <Card>
        <EmptyState
          title="Không tìm thấy thiết bị"
          description="Thiết bị không tồn tại hoặc đã ngưng sử dụng."
        />
      </Card>
    );

  // leader & accountant CHỈ XEM; staff chỉ ghi phòng mình; admin full.
  const canWrite = canWriteEquipmentDept(user, eq.department_id);

  function reloadAll() {
    eqQ.reload();
    calQ.reload();
  }

  async function downloadAttachment(attId: string) {
    try {
      const info = await equipApi.getAttachmentDownload(id, attId);
      window.open(info.download_url, '_blank', 'noopener');
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  async function downloadCert(calibrationId: string) {
    try {
      const info = await equipApi.getCertDownload(calibrationId);
      window.open(info.download_url, '_blank', 'noopener');
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  const records = calQ.data?.data ?? [];

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/equipment')}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Danh sách thiết bị
      </button>

      <PageHeader
        title={eq.name}
        description={`${eq.equipment_code} · ${eq.department_name ?? '—'}`}
        icon={<Wrench size={20} />}
        actions={
          canWrite ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={() => setAttachOpen(true)}>
                <Paperclip size={16} /> Đính kèm tài liệu
              </Button>
              <Button variant="secondary" onClick={() => setEditOpen(true)}>
                <Pencil size={16} /> Sửa thông tin
              </Button>
              <Button onClick={() => setCalibrateOpen(true)}>
                <Plus size={16} /> Ghi hiệu chuẩn
              </Button>
            </div>
          ) : undefined
        }
      />

      {/* Cảnh báo nổi bật khi quá hạn / không đạt */}
      {eq.warning_label && (
        <div className="flex items-center gap-3 rounded-lg border border-overdue/30 bg-overdue/5 px-4 py-3">
          <ShieldCheck size={20} className="shrink-0 text-overdue" />
          <p className="text-sm font-medium text-overdue">{eq.warning_label}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Thông tin thiết bị */}
        <Card>
          <CardHeader title="Thông tin thiết bị" />
          <CardBody className="flex flex-col gap-2.5 text-sm">
            <Row label="Mã thiết bị" value={eq.equipment_code} />
            <Row label="Vị trí" value={eq.location || '—'} />
            <Row label="Phòng ban" value={eq.department_name ?? '—'} />
            <Row label="Người phụ trách" value={eq.responsible_user_name ?? '—'} />
            <Row label="Ngày mua" value={formatDate(eq.purchase_date ?? undefined)} />
            <div className="flex justify-between gap-4">
              <span className="shrink-0 text-subink">Tình trạng</span>
              <EquipmentStatusBadge status={eq.status} />
            </div>
            <Row label="Người tạo" value={eq.created_by_name ?? '—'} />
            <Row label="Ngày tạo" value={formatDate(eq.created_at)} />
          </CardBody>
        </Card>

        {/* Hiệu chuẩn */}
        <Card className="lg:col-span-2">
          <CardHeader title="Tình trạng hiệu chuẩn" subtitle="Liên kết chuẩn đo lường (§6.5)" />
          <CardBody className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs text-subink">Trạng thái</p>
                <div className="mt-1">
                  <CalibrationStatusBadge status={eq.calibration_status} />
                </div>
              </div>
              <div>
                <p className="text-xs text-subink">Chu kỳ</p>
                <p className="mt-1 font-medium text-ink">{cycleLabel(eq)}</p>
              </div>
              <div>
                <p className="text-xs text-subink">Hạn kế tiếp</p>
                <p className="mt-1 font-medium text-ink">
                  {formatDate(eq.next_due_date ?? undefined)}
                  {typeof eq.days_to_due === 'number' && eq.calibration_status !== 'not_applicable' && (
                    <span className="ml-1.5 text-xs text-subink">
                      ({eq.days_to_due < 0 ? `quá ${-eq.days_to_due} ngày` : `còn ${eq.days_to_due} ngày`})
                    </span>
                  )}
                </p>
              </div>
            </div>

            {eq.last_calibration ? (
              <div className="rounded-lg border border-hairline bg-plate/40 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-stem">
                  Lần hiệu chuẩn gần nhất
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-medium text-ink">
                    {formatDate(eq.last_calibration.calibrated_at)}
                  </span>
                  <ResultBadge result={eq.last_calibration.result} />
                  <span className="text-subink">{eq.last_calibration.provider ?? '—'}</span>
                  {eq.last_calibration.cert_attachment_id && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => downloadCert(eq.last_calibration!.id)}
                    >
                      <Download size={14} /> Tải CoC
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-subink">
                {eq.calibration_status === 'not_applicable'
                  ? 'Thiết bị không thuộc diện hiệu chuẩn.'
                  : 'Thiết bị chưa có lần hiệu chuẩn nào.'}
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Lịch sử hiệu chuẩn (immutable) */}
      <Card>
        <CardHeader
          title={`Lịch sử hiệu chuẩn (${records.length})`}
          subtitle="Bản ghi bất biến — không thể sửa hoặc xóa (§8.4). Đính chính bằng cách ghi bản mới."
        />
        <CardBody className="p-0">
          {calQ.loading ? (
            <LoadingState />
          ) : records.length === 0 ? (
            <EmptyState
              title="Chưa có lần hiệu chuẩn"
              description="Ghi lần hiệu chuẩn để bắt đầu theo dõi chu kỳ và hạn kế tiếp."
            />
          ) : (
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-hairline bg-plate/80 text-left text-xs uppercase tracking-wide text-stem">
                    <th className="px-4 py-2.5">Ngày hiệu chuẩn</th>
                    <th className="px-4 py-2.5">Kết quả</th>
                    <th className="px-4 py-2.5">Đơn vị thực hiện</th>
                    <th className="px-4 py-2.5">Hạn kế tiếp</th>
                    <th className="px-4 py-2.5">Người ghi</th>
                    <th className="px-4 py-2.5 text-right">CoC</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {records.map((c) => (
                    <tr key={c.id} className="hover:bg-plate/50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-ink">{formatDate(c.calibrated_at)}</span>
                          {c.is_latest && <Badge tone="info">Gần nhất</Badge>}
                        </div>
                        {c.note && <p className="mt-0.5 text-xs text-subink">{c.note}</p>}
                        {c.correction_of && (
                          <p className="mt-0.5 text-xs text-warning">Đính chính bản ghi trước</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <ResultBadge result={c.result} />
                      </td>
                      <td className="px-4 py-3 text-subink">{c.provider ?? '—'}</td>
                      <td className="px-4 py-3">
                        {formatDate(c.next_due_date ?? undefined)}
                        {c.next_due_overridden && (
                          <span className="ml-1.5 text-xs text-warning" title={c.override_reason ?? undefined}>
                            (ghi đè)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-subink">{c.created_by_name ?? '—'}</td>
                      <td className="px-4 py-3 text-right">
                        {c.cert_attachment_id ? (
                          <Button size="sm" variant="ghost" onClick={() => downloadCert(c.id)}>
                            <Download size={14} /> Tải
                          </Button>
                        ) : (
                          <span className="text-subink">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Tài liệu thiết bị */}
      <Card>
        <CardHeader title={`Tài liệu thiết bị (${eq.attachments?.length ?? 0})`} subtitle="Hướng dẫn sử dụng, ảnh, hồ sơ" />
        <CardBody className="p-0">
          {(eq.attachments ?? []).length === 0 ? (
            <EmptyState title="Chưa có tài liệu đính kèm" />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {(eq.attachments ?? []).map((a) => (
                <li
                  key={a.attachment_id}
                  className="flex items-center justify-between gap-3 px-5 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{a.file_name}</p>
                    <p className="text-xs text-subink">
                      {formatSize(a.size)} · {a.uploaded_by_name ?? '—'} · {formatDateTime(a.uploaded_at)}
                    </p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => downloadAttachment(a.attachment_id)}>
                    <Download size={14} /> Tải
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {editOpen && (
        <EditEquipmentModal
          equipment={eq}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false);
            toast.success('Đã cập nhật thiết bị');
            reloadAll();
          }}
        />
      )}
      {calibrateOpen && (
        <CalibrateModal
          equipment={eq}
          onClose={() => setCalibrateOpen(false)}
          onDone={() => {
            setCalibrateOpen(false);
            toast.success('Đã ghi lần hiệu chuẩn');
            reloadAll();
          }}
        />
      )}
      {attachOpen && (
        <AttachModal
          equipmentId={id}
          onClose={() => setAttachOpen(false)}
          onDone={() => {
            setAttachOpen(false);
            toast.success('Đã đính kèm tài liệu');
            eqQ.reload();
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

function ResultBadge({ result }: { result: CalibrationResult }) {
  return (
    <Badge tone={result === 'pass' ? 'success' : 'overdue'}>
      {CALIBRATION_RESULT_LABELS[result]}
    </Badge>
  );
}

function EditEquipmentModal({
  equipment,
  onClose,
  onSaved,
}: {
  equipment: EquipmentDetailType;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(equipment.name);
  const [location, setLocation] = useState(equipment.location ?? '');
  const [responsibleId, setResponsibleId] = useState(equipment.responsible_user_id ?? '');
  const [purchaseDate, setPurchaseDate] = useState(equipment.purchase_date ?? '');
  const [status, setStatus] = useState<EquipmentStatus>(equipment.status);
  const [cycleValue, setCycleValue] = useState(
    equipment.calibration_cycle_value ? String(equipment.calibration_cycle_value) : '',
  );
  const [cycleUnit, setCycleUnit] = useState<CalibrationCycleUnit>(
    equipment.calibration_cycle_unit ?? 'month',
  );
  const [submitting, setSubmitting] = useState(false);

  // Người phụ trách phải cùng phòng với thiết bị (BR-EQP-013).
  const { data: users } = useAsync(
    () =>
      equipment.department_id
        ? usersApi.listUsers({ department_id: equipment.department_id, limit: 100 })
        : Promise.resolve({ data: [], meta: undefined } as never),
    [equipment.department_id],
  );

  async function submit() {
    if (!name.trim()) return toast.error('Nhập tên thiết bị');
    if (cycleValue && Number(cycleValue) <= 0) return toast.error('Chu kỳ phải lớn hơn 0');
    setSubmitting(true);
    try {
      await equipApi.updateEquipment(equipment.id, {
        name: name.trim(),
        location: location.trim() || null,
        responsible_user_id: responsibleId || null,
        purchase_date: purchaseDate || null,
        status,
        calibration_cycle_value: cycleValue ? Number(cycleValue) : null,
        calibration_cycle_unit: cycleValue ? cycleUnit : null,
      });
      onSaved();
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
      size="lg"
      title="Sửa thông tin thiết bị"
      description="Mã thiết bị và phòng ban không thể thay đổi. Đổi chu kỳ chỉ áp dụng cho lần hiệu chuẩn tiếp theo."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tên thiết bị" required className="sm:col-span-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Vị trí đặt" className="sm:col-span-2">
          <Input value={location} onChange={(e) => setLocation(e.target.value)} />
        </Field>
        <Field label="Người phụ trách" hint="Phải cùng phòng với thiết bị.">
          <Select value={responsibleId} onChange={(e) => setResponsibleId(e.target.value)}>
            <option value="">— Bỏ người phụ trách —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ngày mua">
          <Input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
        </Field>
        <Field label="Tình trạng">
          <Select value={status} onChange={(e) => setStatus(e.target.value as EquipmentStatus)}>
            {(Object.keys(EQUIPMENT_STATUS_LABELS) as EquipmentStatus[]).map((s) => (
              <option key={s} value={s}>
                {EQUIPMENT_STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Chu kỳ hiệu chuẩn" hint="Bỏ trống = không diện hiệu chuẩn.">
          <div className="flex gap-3">
            <Input
              value={cycleValue}
              onChange={(e) => setCycleValue(e.target.value.replace(/[^\d]/g, ''))}
              inputMode="numeric"
              placeholder="vd: 12"
              className="max-w-[120px]"
            />
            <Select
              value={cycleUnit}
              onChange={(e) => setCycleUnit(e.target.value as CalibrationCycleUnit)}
            >
              {(Object.keys(CALIBRATION_CYCLE_UNIT_LABELS) as CalibrationCycleUnit[]).map((u) => (
                <option key={u} value={u}>
                  {CALIBRATION_CYCLE_UNIT_LABELS[u]}
                </option>
              ))}
            </Select>
          </div>
        </Field>
      </div>
    </Modal>
  );
}

function CalibrateModal({
  equipment,
  onClose,
  onDone,
}: {
  equipment: EquipmentDetailType;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const today = new Date().toISOString().slice(0, 10);
  const [calibratedAt, setCalibratedAt] = useState(today);
  const [provider, setProvider] = useState('');
  const [result, setResult] = useState<CalibrationResult>('pass');
  const [useOverride, setUseOverride] = useState(false);
  const [nextDueOverride, setNextDueOverride] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [note, setNote] = useState('');
  const [cert, setCert] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const hasCycle = !!equipment.calibration_cycle_value && !!equipment.calibration_cycle_unit;

  async function submit() {
    if (!calibratedAt) return toast.error('Chọn ngày hiệu chuẩn');
    if (calibratedAt > today) return toast.error('Ngày hiệu chuẩn không được ở tương lai');
    if (result === 'pass' && !cert) return toast.error('Cần đính kèm giấy chứng nhận (CoC) khi Đạt');
    if (!hasCycle && !useOverride)
      return toast.error('Thiết bị chưa có chu kỳ — hãy nhập ngày kế tiếp thủ công');
    if (useOverride) {
      if (!nextDueOverride) return toast.error('Nhập ngày hiệu chuẩn kế tiếp');
      if (nextDueOverride <= calibratedAt)
        return toast.error('Ngày kế tiếp phải sau ngày hiệu chuẩn');
      if (!overrideReason.trim()) return toast.error('Nhập lý do ghi đè ngày kế tiếp');
    }
    setSubmitting(true);
    try {
      await equipApi.createCalibration(equipment.id, {
        calibrated_at: calibratedAt,
        result,
        provider: provider.trim() || null,
        next_due_date_override: useOverride ? nextDueOverride : null,
        override_reason: useOverride ? overrideReason.trim() : null,
        note: note.trim() || null,
        cert: cert ?? null,
      });
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
      size="lg"
      title="Ghi lần hiệu chuẩn"
      description="Bản ghi sẽ bất biến sau khi tạo. Hạn kế tiếp tự tính theo chu kỳ trừ khi bạn ghi đè."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Ghi hiệu chuẩn
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Ngày hiệu chuẩn" required>
          <Input
            type="date"
            max={today}
            value={calibratedAt}
            onChange={(e) => setCalibratedAt(e.target.value)}
          />
        </Field>
        <Field label="Kết quả" required>
          <Select value={result} onChange={(e) => setResult(e.target.value as CalibrationResult)}>
            <option value="pass">{CALIBRATION_RESULT_LABELS.pass}</option>
            <option value="fail">{CALIBRATION_RESULT_LABELS.fail}</option>
          </Select>
        </Field>
        <Field label="Đơn vị thực hiện" className="sm:col-span-2">
          <Input
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder="vd: Trung tâm Đo lường ABC"
          />
        </Field>

        <div className="sm:col-span-2 rounded-lg border border-hairline bg-plate/30 px-4 py-3">
          <p className="text-xs text-subink">
            {hasCycle
              ? `Hạn kế tiếp tự tính = ngày hiệu chuẩn + ${equipment.calibration_cycle_value} ${equipment.calibration_cycle_unit ? CALIBRATION_CYCLE_UNIT_LABELS[equipment.calibration_cycle_unit] : ''}.`
              : 'Thiết bị chưa cấu hình chu kỳ — bắt buộc ghi đè ngày kế tiếp.'}
          </p>
          <label className="mt-2 flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={useOverride || !hasCycle}
              disabled={!hasCycle}
              onChange={(e) => setUseOverride(e.target.checked)}
            />
            Ghi đè ngày hiệu chuẩn kế tiếp
          </label>
        </div>

        {(useOverride || !hasCycle) && (
          <>
            <Field label="Ngày kế tiếp (ghi đè)" required>
              <Input
                type="date"
                min={calibratedAt}
                value={nextDueOverride}
                onChange={(e) => setNextDueOverride(e.target.value)}
              />
            </Field>
            <Field label="Lý do ghi đè" required>
              <Input
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="vd: Theo ngày ghi trên CoC"
              />
            </Field>
          </>
        )}

        <Field label="Ghi chú" className="sm:col-span-2">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="vd: lý do đính chính" />
        </Field>
        <Field
          label="Giấy chứng nhận (CoC)"
          required={result === 'pass'}
          className="sm:col-span-2"
          hint="PDF, PNG, JPG · tối đa 20MB. Bắt buộc khi kết quả Đạt."
        >
          <FileDrop file={cert} onSelect={setCert} accept={CERT_ACCEPT} />
        </Field>
      </div>
    </Modal>
  );
}

function AttachModal({
  equipmentId,
  onClose,
  onDone,
}: {
  equipmentId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<'manual' | 'image' | 'other'>('manual');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!file) return toast.error('Chọn tệp tài liệu');
    if (file.size > MAX_FILE_MB * 1024 * 1024) return toast.error(`Tệp vượt quá ${MAX_FILE_MB}MB`);
    setSubmitting(true);
    try {
      await equipApi.addEquipmentAttachment(equipmentId, { file, doc_type: docType });
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
      title="Đính kèm tài liệu thiết bị"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tải lên
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Phân loại">
          <Select value={docType} onChange={(e) => setDocType(e.target.value as 'manual' | 'image' | 'other')}>
            <option value="manual">Hướng dẫn sử dụng</option>
            <option value="image">Ảnh</option>
            <option value="other">Khác</option>
          </Select>
        </Field>
        <Field label="Tệp tài liệu" required hint="PDF, DOCX, XLSX, PNG, JPG · tối đa 20MB">
          <FileDrop file={file} onSelect={setFile} accept={ATTACH_ACCEPT} />
        </Field>
      </div>
    </Modal>
  );
}

/** Ô chọn tệp dùng chung (đồng bộ style FileDrop của M3). */
function FileDrop({
  file,
  onSelect,
  accept,
}: {
  file: File | null;
  onSelect: (f: File | null) => void;
  accept: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-hairline bg-plate/40 px-4 py-3 text-sm hover:bg-plate">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blueberry/10 text-blueberry">
        <UploadCloud size={18} />
      </span>
      <span className="min-w-0 flex-1">
        {file ? (
          <span className="truncate font-medium text-ink">{file.name}</span>
        ) : (
          <span className="text-subink">Bấm để chọn tệp…</span>
        )}
      </span>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
