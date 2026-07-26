import { useState } from 'react';
import { FlaskConical, Plus, Pencil, Trash2, BadgeCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Badge } from '@/components/ui/Badge';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatMoney } from '@/lib/format';
import { canManageTestParameters } from '@/lib/rbac';
import { TEST_MATRIX_LABELS, type TestMatrix, type TestParameter } from '@/types';
import * as flowApi from '@/api/sampleFlow';
import * as deptApi from '@/api/users';

const MATRICES = Object.keys(TEST_MATRIX_LABELS) as TestMatrix[];

/**
 * Danh mục CHỈ TIÊU THỬ NGHIỆM (master data, m27) — nguồn: Bảng giá phân tích.
 * Phòng nhận mẫu / Ban lãnh đạo / Quản trị: toàn quyền. Vai trò khác: chỉ xem.
 */
export function TestParameters() {
  const { user } = useAuth();
  const toast = useToast();
  const canManage = canManageTestParameters(user);

  const [q, setQ] = useState('');
  const [matrix, setMatrix] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<string>('true');
  const [unassigned, setUnassigned] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TestParameter | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TestParameter | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () =>
      flowApi.listTestParameters({
        q: q || undefined,
        matrix: matrix || undefined,
        is_active: activeFilter === '' ? undefined : activeFilter === 'true',
        unassigned: unassigned || undefined,
        limit: 200,
      }),
    [q, matrix, activeFilter, unassigned],
  );

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await flowApi.deleteTestParameter(deleteTarget.id);
      toast.success('Đã xóa chỉ tiêu', 'Nếu chỉ tiêu đã dùng trong phiếu chuyển mẫu, hệ thống chỉ ngưng sử dụng để giữ dữ liệu lịch sử.');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<TestParameter>[] = [
    {
      key: 'name',
      header: 'Chỉ tiêu thử nghiệm',
      sortValue: (p) => p.name,
      render: (p) => (
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-medium text-ink">{p.name}</span>
            {p.is_accredited && (
              <span title="Chỉ tiêu được công nhận VILAS" className="shrink-0 text-success">
                <BadgeCheck size={14} />
              </span>
            )}
            {!p.is_active && <Badge tone="muted">Ngưng dùng</Badge>}
          </div>
          {p.sample_matrix && <p className="text-xs text-subink">{p.sample_matrix}</p>}
        </div>
      ),
    },
    { key: 'matrix', priority: 1, header: 'Nhóm nền mẫu', render: (p) => <Badge tone="info">{p.matrix_label}</Badge> },
    { key: 'method', header: 'Phương pháp', render: (p) => <span className="text-subink">{p.method ?? '—'}</span> },
    {
      key: 'price',
      priority: 1,
      header: 'Đơn giá',
      align: 'right',
      sortValue: (p) => Number(p.unit_price ?? 0),
      render: (p) => (p.unit_price ? <span className="font-medium text-ink">{formatMoney(p.unit_price)}</span> : '—'),
    },
    { key: 'dept', header: 'Phòng lab', render: (p) => p.department_name ?? <span className="text-warning">Chưa gán</span> },
    { key: 'tat', header: 'TG (ngày)', align: 'center', render: (p) => p.turnaround_days ?? '—' },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (p: TestParameter) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(p)}><Pencil size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(p)}>
                  <Trash2 size={14} className="text-overdue" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Chỉ tiêu thử nghiệm"
        description="Danh mục chỉ tiêu · phương pháp · đơn giá — dùng để phân chỉ tiêu chuyển phòng lab"
        icon={<FlaskConical size={20} />}
        actions={canManage && <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Thêm chỉ tiêu</Button>}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tên chỉ tiêu / phương pháp…" className="max-w-xs" />
          <Select value={matrix} onChange={(e) => setMatrix(e.target.value)} className="w-full sm:max-w-[240px]">
            <option value="">— Mọi nhóm nền mẫu —</option>
            {MATRICES.map((m) => <option key={m} value={m}>{TEST_MATRIX_LABELS[m]}</option>)}
          </Select>
          <Select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className="w-full sm:max-w-[170px]">
            <option value="true">Đang dùng</option>
            <option value="false">Ngưng dùng</option>
            <option value="">Tất cả</option>
          </Select>
          <label className="flex items-center gap-1.5 text-sm text-subink">
            <input type="checkbox" checked={unassigned} onChange={(e) => setUnassigned(e.target.checked)} />
            Chưa gán phòng lab
          </label>
          <span className="ml-auto text-sm text-subink">{data?.meta?.total ?? 0} chỉ tiêu</span>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(p) => p.id} loading={loading} pageSize={20} />
      </Card>

      {createOpen && (
        <ParameterModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => { setCreateOpen(false); reload(); toast.success('Đã thêm chỉ tiêu'); }}
        />
      )}
      {editTarget && (
        <ParameterModal
          parameter={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => { setEditTarget(null); reload(); toast.success('Đã cập nhật'); }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa chỉ tiêu"
        message={`Xóa "${deleteTarget?.name ?? ''}" khỏi danh mục? Nếu chỉ tiêu đã được dùng trong phiếu chuyển mẫu, hệ thống sẽ chuyển sang trạng thái "Ngưng dùng" thay vì xóa.`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function ParameterModal({
  parameter, onClose, onSaved,
}: {
  parameter?: TestParameter;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!parameter;
  const { data: depts } = useAsync(() => deptApi.listDepartments(), []);
  const [f, setF] = useState({
    matrix: parameter?.matrix ?? ('other' as string),
    name: parameter?.name ?? '',
    sample_matrix: parameter?.sample_matrix ?? '',
    method: parameter?.method ?? '',
    unit: parameter?.unit ?? '',
    unit_price: parameter?.unit_price ?? '',
    turnaround_days: parameter?.turnaround_days?.toString() ?? '',
    in_charge: parameter?.in_charge ?? '',
    note: parameter?.note ?? '',
    department_id: parameter?.department_id ?? '',
    is_accredited: parameter?.is_accredited ?? false,
    is_active: parameter?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  async function submit() {
    if (!f.name.trim()) return toast.error('Nhập tên chỉ tiêu');
    setSaving(true);
    try {
      const body = {
        matrix: f.matrix,
        name: f.name.trim(),
        sample_matrix: f.sample_matrix.trim() || null,
        method: f.method.trim() || null,
        unit: f.unit.trim() || null,
        unit_price: f.unit_price.toString().trim() || null,
        turnaround_days: f.turnaround_days ? Number(f.turnaround_days) : null,
        in_charge: f.in_charge.trim() || null,
        note: f.note.trim() || null,
        department_id: f.department_id || null,
        is_accredited: f.is_accredited,
        is_active: f.is_active,
      };
      if (editing) await flowApi.updateTestParameter(parameter!.id, body);
      else await flowApi.createTestParameter(body);
      onSaved();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setSaving(false);
    }
  }

  const labs = (depts?.data ?? []).filter((d) => d.kind === 'lab' || d.kind === 'division');

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={editing ? 'Sửa chỉ tiêu thử nghiệm' : 'Thêm chỉ tiêu thử nghiệm'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button onClick={submit} loading={saving}>{editing ? 'Lưu' : 'Thêm'}</Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Nhóm nền mẫu" required>
          <Select value={f.matrix} onChange={set('matrix')}>
            {MATRICES.map((m) => <option key={m} value={m}>{TEST_MATRIX_LABELS[m]}</option>)}
          </Select>
        </Field>
        <Field label="Phòng lab thực hiện" hint="Dùng để tự chọn phòng khi chuyển mẫu">
          <Select value={f.department_id} onChange={set('department_id')}>
            <option value="">— Chưa gán —</option>
            {labs.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </Select>
        </Field>
        <Field label="Tên chỉ tiêu" required className="md:col-span-2">
          <Input value={f.name} onChange={set('name')} placeholder="VD: pH (H2O), Coliforms (MPN)…" />
        </Field>
        <Field label="Phương pháp thử nghiệm" className="md:col-span-2">
          <Input value={f.method} onChange={set('method')} placeholder="VD: TCVN 5979:2007" />
        </Field>
        <Field label="Nền mẫu chi tiết" className="md:col-span-2" hint="Dùng cho SHPT: mô/máu/phân…">
          <Input value={f.sample_matrix} onChange={set('sample_matrix')} />
        </Field>
        <Field label="Đơn giá (VNĐ)">
          <Input value={f.unit_price} onChange={set('unit_price')} placeholder="160000" />
        </Field>
        <Field label="Đơn vị">
          <Input value={f.unit} onChange={set('unit')} placeholder="mg/kg, CFU/g…" />
        </Field>
        <Field label="Thời gian trả KQ (ngày)">
          <Input type="number" min={0} value={f.turnaround_days} onChange={set('turnaround_days')} />
        </Field>
        <Field label="Người phụ trách">
          <Input value={f.in_charge} onChange={set('in_charge')} placeholder="VD: Cô Hà" />
        </Field>
        <Field label="Ghi chú" className="md:col-span-2">
          <Textarea rows={2} value={f.note} onChange={set('note')} />
        </Field>
        <div className="md:col-span-2 flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={f.is_accredited}
              onChange={(e) => setF((p) => ({ ...p, is_accredited: e.target.checked }))}
            />
            Được công nhận VILAS
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={f.is_active}
              onChange={(e) => setF((p) => ({ ...p, is_active: e.target.checked }))}
            />
            Đang sử dụng
          </label>
        </div>
      </div>
    </Modal>
  );
}
