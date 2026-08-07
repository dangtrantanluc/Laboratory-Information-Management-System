import { useState } from 'react';
import { ErrorState } from '@/components/ui/States';
import { useNavigate } from 'react-router-dom';
import { FlaskConical, Plus, FileSpreadsheet } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { FilterBar } from '@/components/ui/FilterBar';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { ChemicalStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDecimal } from '@/lib/format';
import { canManageChemical, canViewCost } from '@/lib/rbac';
import { MEASUREMENT_GROUP_LABELS, type Chemical } from '@/types';
import * as chemApi from '@/api/chemicals';
import * as usersApi from '@/api/users';

export function Chemicals() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [group, setGroup] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () =>
      chemApi.listChemicals({
        q: dq || undefined,
        measurement_group: group || undefined,
        limit: 100,
      }),
    [dq, group],
  );

  const columns: Column<Chemical>[] = [
    {
      key: 'name',
      header: 'Tên hóa chất',
      sortValue: (c) => c.name,
      render: (c) => (
        <div>
          <p className="font-semibold text-ink">{c.name}</p>
          {c.cas_no && <p className="text-xs text-subink">CAS {c.cas_no}</p>}
        </div>
      ),
    },
    { key: 'department_name', header: 'Phòng', render: (c) => c.department_name ?? '—' },
    {
      key: 'group',
      header: 'Nhóm đo',
      render: (c) => <Badge tone="neutral">{MEASUREMENT_GROUP_LABELS[c.measurement_group]}</Badge>,
    },
    {
      key: 'stock',
      priority: 1,
      header: 'Tồn (cơ sở)',
      align: 'right',
      sortValue: (c) => Number(c.total_stock_base),
      render: (c) => (
        <span className="font-medium">
          {formatDecimal(c.total_stock_base)} {c.base_unit}
        </span>
      ),
    },
    { key: 'lot_count', header: 'Số lô', align: 'center', render: (c) => c.lot_count },
    { key: 'status', priority: 1, header: 'Trạng thái', render: (c) => <ChemicalStatusBadge status={c.status} /> },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hóa chất"
        description="Danh mục hóa chất, lô, giá và tồn kho"
        icon={<FlaskConical size={20} />}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setExportOpen(true)}>
              <FileSpreadsheet size={16} /> Xuất Excel
            </Button>
            {canManageChemical(user) && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} /> Thêm hóa chất
              </Button>
            )}
          </div>
        }
      />

      <Card>
        <FilterBar
          search={<SearchInput value={q} onChange={setQ} placeholder="Tên hoặc CAS…" />}
          filters={[
            {
              key: 'group',
              label: 'Nhóm đo',
              active: !!group,
              node: (
                <Select value={group} onChange={(e) => setGroup(e.target.value)}>
                  <option value="">Mọi nhóm đo</option>
                  <option value="mass">Khối lượng</option>
                  <option value="volume">Thể tích</option>
                  <option value="count">Đếm</option>
                </Select>
              ),
            },
          ]}
          onClear={() => setGroup('')}
        />
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          knownTotal={data?.meta?.total}
          empty={error ? <ErrorState error={error} onRetry={reload} /> : undefined}
          rowKey={(c) => c.id}
          loading={loading}
          pageSize={12}
          onRowClick={(c) => navigate(`/chemicals/${c.id}`)}
        />
      </Card>

      {createOpen && (
        <CreateChemicalModal
          canCost={canViewCost(user)}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm hóa chất');
          }}
        />
      )}
      {exportOpen && <ExportModal onClose={() => setExportOpen(false)} />}
    </div>
  );
}

function CreateChemicalModal({
  onClose,
  onCreated,
}: {
  canCost: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState('');
  const [cas, setCas] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [baseUnit, setBaseUnit] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [threshold, setThreshold] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: units } = useAsync(() => chemApi.listUnits(), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!name.trim()) return toast.error('Nhập tên hóa chất');
    if (!baseUnit) return toast.error('Chọn đơn vị cơ sở');
    setSubmitting(true);
    try {
      await chemApi.createChemical({
        name: name.trim(),
        cas_no: cas || null,
        manufacturer: manufacturer || null,
        base_unit: baseUnit,
        department_id: departmentId || null,
        reorder_threshold: threshold || null,
      });
      onCreated();
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
      title="Thêm hóa chất"
      description="Nhóm đo được suy ra từ đơn vị cơ sở."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Tên hóa chất" required className="md:col-span-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="vd: NaCl" />
        </Field>
        <Field label="Số CAS">
          <Input value={cas} onChange={(e) => setCas(e.target.value)} placeholder="7647-14-5" />
        </Field>
        <Field label="Hãng sản xuất">
          <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} placeholder="Merck" />
        </Field>
        <Field label="Đơn vị cơ sở" required>
          <Select value={baseUnit} onChange={(e) => setBaseUnit(e.target.value)}>
            <option value="">— Chọn —</option>
            {(units ?? []).map((u) => (
              <option key={u.code} value={u.code}>
                {u.label} ({u.code})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Phòng ban">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">— Không chọn —</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ngưỡng cảnh báo tồn (theo đơn vị cơ sở)" className="md:col-span-2">
          <Input value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder="vd: 50000" inputMode="decimal" />
        </Field>
      </div>
    </Modal>
  );
}

function ExportModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!from || !to) return toast.error('Chọn khoảng thời gian');
    setSubmitting(true);
    try {
      await chemApi.exportTransactionsXlsx({ date_from: from, date_to: to });
      toast.success('Đã tải file Excel');
      onClose();
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
      title="Xuất Excel nhật ký giao dịch"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tải Excel
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Từ ngày" required>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="Đến ngày" required>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
