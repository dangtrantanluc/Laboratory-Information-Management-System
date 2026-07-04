import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wrench, Plus, AlertTriangle, PlayCircle } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select } from '@/components/ui/Field';
import { EquipmentStatusBadge, CalibrationStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canWriteEquipment, canRunCalibrationCron } from '@/lib/rbac';
import {
  EQUIPMENT_STATUS_LABELS,
  CALIBRATION_STATUS_LABELS,
  CALIBRATION_CYCLE_UNIT_LABELS,
  type CalibrationCycleUnit,
  type EquipmentListItem,
  type EquipmentStatus,
} from '@/types';
import * as equipApi from '@/api/equipment';
import * as usersApi from '@/api/users';

export function Equipment() {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<EquipmentStatus | ''>('');
  const [calStatus, setCalStatus] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [onlyDue, setOnlyDue] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () =>
      onlyDue
        ? equipApi.listCalibrationDue({
            department_id: departmentId || undefined,
            bucket: 'all',
            limit: 100,
          })
        : equipApi.listEquipments({
            q: q || undefined,
            status: status || undefined,
            calibration_status: (calStatus || undefined) as never,
            department_id: departmentId || undefined,
            limit: 100,
          }),
    [q, status, calStatus, departmentId, onlyDue],
  );
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  const canCreate = canWriteEquipment(user); // admin/staff; staff scope kiểm tại server + ẩn theo phòng khi tạo

  const columns: Column<EquipmentListItem>[] = [
    {
      key: 'equipment_code',
      header: 'Mã / Tên',
      sortValue: (e) => e.equipment_code,
      render: (e) => (
        <div>
          <p className="font-semibold text-ink">{e.name}</p>
          <p className="text-xs text-subink">{e.equipment_code}</p>
        </div>
      ),
    },
    { key: 'department', header: 'Phòng', render: (e) => e.department_name ?? '—' },
    {
      key: 'responsible',
      header: 'Người phụ trách',
      render: (e) => e.responsible_user_name ?? '—',
    },
    {
      key: 'status',
      header: 'Tình trạng',
      align: 'center',
      render: (e) => <EquipmentStatusBadge status={e.status} />,
    },
    {
      key: 'calibration',
      header: 'Hiệu chuẩn',
      render: (e) => (
        <div className="flex flex-col gap-1">
          <CalibrationStatusBadge status={e.calibration_status} />
          {e.warning_label && <span className="text-xs text-overdue">{e.warning_label}</span>}
        </div>
      ),
    },
    {
      key: 'next_due_date',
      header: 'Hạn kế tiếp',
      sortValue: (e) => e.next_due_date ?? '',
      render: (e) => formatDate(e.next_due_date ?? undefined),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Thiết bị & Hiệu chuẩn"
        description="Quản lý thiết bị và liên kết chuẩn đo lường theo ISO/IEC 17025 (§6.4 / §6.5)"
        icon={<Wrench size={20} />}
        actions={
          <div className="flex items-center gap-2">
            {canRunCalibrationCron(user) && (
              <Button variant="secondary" onClick={() => setCronOpen(true)}>
                <PlayCircle size={16} /> Chạy nhắc hiệu chuẩn
              </Button>
            )}
            {canCreate && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} /> Thêm thiết bị
              </Button>
            )}
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput
            value={q}
            onChange={setQ}
            placeholder="Mã hoặc tên thiết bị…"
            className="max-w-xs flex-1"
          />
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value as EquipmentStatus | '')}
            className="max-w-[180px]"
            disabled={onlyDue}
          >
            <option value="">Mọi tình trạng</option>
            {(Object.keys(EQUIPMENT_STATUS_LABELS) as EquipmentStatus[]).map((s) => (
              <option key={s} value={s}>
                {EQUIPMENT_STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
          <Select
            value={calStatus}
            onChange={(e) => setCalStatus(e.target.value)}
            className="max-w-[200px]"
            disabled={onlyDue}
          >
            <option value="">Mọi trạng thái hiệu chuẩn</option>
            <option value="ok">{CALIBRATION_STATUS_LABELS.ok}</option>
            <option value="due_soon">{CALIBRATION_STATUS_LABELS.due_soon}</option>
            <option value="overdue">{CALIBRATION_STATUS_LABELS.overdue}</option>
            <option value="failed">{CALIBRATION_STATUS_LABELS.failed}</option>
            <option value="never_calibrated">{CALIBRATION_STATUS_LABELS.never_calibrated}</option>
            <option value="not_applicable">{CALIBRATION_STATUS_LABELS.not_applicable}</option>
          </Select>
          <Select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="max-w-[180px]"
          >
            <option value="">Mọi phòng</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          <Button
            variant={onlyDue ? 'danger' : 'secondary'}
            onClick={() => setOnlyDue((v) => !v)}
            title="Lọc thiết bị sắp/đã quá hạn hiệu chuẩn"
          >
            <AlertTriangle size={16} /> {onlyDue ? 'Đang lọc tới hạn' : 'Sắp tới hạn'}
          </Button>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(e) => e.id}
          onRowClick={(e) => navigate(`/equipment/${e.id}`)}
          loading={loading}
          pageSize={12}
        />
      </Card>

      {createOpen && (
        <CreateEquipmentModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => {
            setCreateOpen(false);
            toast.success('Đã thêm thiết bị');
            navigate(`/equipment/${id}`);
          }}
        />
      )}
      {cronOpen && (
        <RunCronModal
          onClose={() => setCronOpen(false)}
          onDone={() => {
            setCronOpen(false);
            reload();
          }}
        />
      )}
    </div>
  );
}

function CreateEquipmentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [departmentId, setDepartmentId] = useState(user?.department?.id ?? '');
  const [responsibleId, setResponsibleId] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [status, setStatus] = useState<EquipmentStatus>('active');
  const [cycleValue, setCycleValue] = useState('');
  const [cycleUnit, setCycleUnit] = useState<CalibrationCycleUnit>('month');
  const [submitting, setSubmitting] = useState(false);

  // admin chọn phòng; staff cố định phòng mình (BE enforce).
  const canPickDept = user?.role === 'admin';
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);
  // Người phụ trách phải cùng phòng với thiết bị (BR-EQP-013).
  const effectiveDept = canPickDept ? departmentId : (user?.department?.id ?? '');
  const { data: users } = useAsync(
    () => (effectiveDept ? usersApi.listUsers({ department_id: effectiveDept, limit: 100 }) : Promise.resolve({ data: [], meta: undefined } as never)),
    [effectiveDept],
  );

  async function submit() {
    if (!name.trim()) return toast.error('Nhập tên thiết bị');
    if (cycleValue && Number(cycleValue) <= 0) return toast.error('Chu kỳ phải lớn hơn 0');
    setSubmitting(true);
    try {
      const res = await equipApi.createEquipment({
        name: name.trim(),
        location: location.trim() || null,
        department_id: canPickDept ? departmentId || undefined : undefined,
        responsible_user_id: responsibleId || null,
        purchase_date: purchaseDate || null,
        status,
        calibration_cycle_value: cycleValue ? Number(cycleValue) : null,
        calibration_cycle_unit: cycleValue ? cycleUnit : null,
      });
      onCreated(res.id);
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
      title="Thêm thiết bị"
      description="Mã thiết bị do hệ thống tự sinh và không thể thay đổi sau khi tạo."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo thiết bị
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tên thiết bị" required className="sm:col-span-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="vd: Máy đo pH Mettler" />
        </Field>
        <Field label="Vị trí đặt" className="sm:col-span-2">
          <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="vd: Phòng Hóa lý - Bàn 3" />
        </Field>
        {canPickDept ? (
          <Field label="Phòng ban sở hữu">
            <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">— Mặc định theo người tạo —</option>
              {(depts?.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Phòng ban sở hữu" hint="Thiết bị thuộc phòng của bạn.">
            <Input value={user?.department?.name ?? '—'} disabled />
          </Field>
        )}
        <Field label="Người phụ trách" hint="Phải cùng phòng với thiết bị.">
          <Select value={responsibleId} onChange={(e) => setResponsibleId(e.target.value)}>
            <option value="">— Chưa chỉ định —</option>
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
        <Field
          label="Chu kỳ hiệu chuẩn"
          className="sm:col-span-2"
          hint="Bỏ trống nếu thiết bị không thuộc diện hiệu chuẩn (sẽ không nhắc/không cảnh báo quá hạn)."
        >
          <div className="flex gap-3">
            <Input
              value={cycleValue}
              onChange={(e) => setCycleValue(e.target.value.replace(/[^\d]/g, ''))}
              inputMode="numeric"
              placeholder="vd: 12"
              className="max-w-[140px]"
            />
            <Select
              value={cycleUnit}
              onChange={(e) => setCycleUnit(e.target.value as CalibrationCycleUnit)}
              className="max-w-[160px]"
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

function RunCronModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [asOf, setAsOf] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<equipApi.RunCalibrationDueResult | null>(null);

  async function run() {
    setRunning(true);
    try {
      const res = await equipApi.runCalibrationDueCron(asOf || undefined);
      setResult(res);
      toast.success(`Đã tạo ${res.notifications_created} thông báo nhắc hiệu chuẩn`);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Chạy nhắc hiệu chuẩn (CRON-5)"
      description="Quét thiết bị tới hạn 30/15/7 ngày và gửi thông báo in-app cho người phụ trách và trưởng nhóm phòng."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={running}>
            {result ? 'Đóng' : 'Hủy'}
          </Button>
          {!result && (
            <Button onClick={run} loading={running}>
              Chạy ngay
            </Button>
          )}
        </>
      }
    >
      {result ? (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="Thiết bị quét" value={result.scanned_equipments} />
          <Stat label="Thông báo tạo" value={result.notifications_created} />
          <Stat label="Người nhận" value={result.recipients} />
          <Stat label="Bỏ qua (không người nhận)" value={result.skipped_no_recipient} />
          <Stat label="Bỏ qua (ngưng/không chu kỳ)" value={result.skipped_retired_or_no_cycle} />
          <Stat label="Khử trùng lặp" value={result.deduped} />
        </div>
      ) : (
        <Field label="Mốc thời gian (tùy chọn — chỉ test)" hint="Bỏ trống để dùng hôm nay.">
          <Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </Field>
      )}
      {result && (
        <div className="mt-3 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onDone}>
            Tải lại danh sách
          </Button>
        </div>
      )}
    </Modal>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-hairline bg-plate/40 px-3 py-2.5">
      <p className="text-xl font-bold text-ink">{value}</p>
      <p className="text-xs text-subink">{label}</p>
    </div>
  );
}
