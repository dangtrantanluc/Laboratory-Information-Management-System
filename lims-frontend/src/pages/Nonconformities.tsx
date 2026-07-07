import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, Plus, PlayCircle } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { NcSeverityBadge, NcStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import { canCreateNC, canRunCapaCron } from '@/lib/rbac';
import {
  NC_SEVERITY_LABELS,
  NC_STATUS_LABELS,
  NC_SOURCE_LABELS,
  type NcListItem,
  type NcSeverity,
  type NcSource,
  type NcStatus,
} from '@/types';
import * as ncApi from '@/api/nonconformities';
import * as usersApi from '@/api/users';

export function Nonconformities() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<NcStatus | ''>('');
  const [severity, setSeverity] = useState<NcSeverity | ''>('');
  const [sourceType, setSourceType] = useState<NcSource | ''>('');
  const [createOpen, setCreateOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () =>
      ncApi.listNonconformities({
        q: q || undefined,
        status: status || undefined,
        severity: severity || undefined,
        source_type: sourceType || undefined,
        limit: 100,
      }),
    [q, status, severity, sourceType],
  );
  const { data: stats } = useAsync(() => ncApi.getNcStats(), []);

  const columns: Column<NcListItem>[] = [
    {
      key: 'nc_code',
      header: 'Mã / Tiêu đề',
      sortValue: (n) => n.nc_code,
      render: (n) => (
        <div>
          <p className="font-semibold text-ink">{n.title}</p>
          <p className="text-xs text-subink">{n.nc_code}</p>
        </div>
      ),
    },
    { key: 'source', header: 'Nguồn', render: (n) => n.source_label },
    {
      key: 'severity',
      header: 'Mức độ',
      align: 'center',
      render: (n) => <NcSeverityBadge severity={n.severity} />,
    },
    {
      key: 'status',
      header: 'Trạng thái',
      align: 'center',
      render: (n) => <NcStatusBadge status={n.status} />,
    },
    { key: 'department', header: 'Phòng', render: (n) => n.department_name ?? '—' },
    { key: 'raised_by', header: 'Người mở', render: (n) => n.raised_by_name ?? '—' },
    {
      key: 'raised_at',
      header: 'Thời điểm',
      sortValue: (n) => n.raised_at,
      render: (n) => formatDateTime(n.raised_at),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Không phù hợp & Hành động khắc phục (CAPA)"
        description="Ghi nhận, phân tích nguyên nhân gốc và khắc phục theo ISO/IEC 17025 (§7.10 / §8.7)"
        icon={<ShieldAlert size={20} />}
        actions={
          <div className="flex items-center gap-2">
            {canRunCapaCron(user) && (
              <Button variant="secondary" onClick={() => setCronOpen(true)}>
                <PlayCircle size={16} /> Nhắc CAPA tới hạn
              </Button>
            )}
            {canCreateNC(user) && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} /> Ghi nhận NC
              </Button>
            )}
          </div>
        }
      />

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Tổng NC" value={stats.total} />
          <StatCard label="Đang khắc phục" value={stats.by_status.in_capa ?? 0} tone="pending" />
          <StatCard label="Đã đóng" value={stats.by_status.closed ?? 0} tone="success" />
          <StatCard label="Nghiêm trọng" value={stats.by_severity.critical ?? 0} tone="overdue" />
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput
            value={q}
            onChange={setQ}
            placeholder="Mã NC hoặc tiêu đề…"
            className="max-w-xs flex-1"
          />
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value as NcStatus | '')}
            className="max-w-[180px]"
          >
            <option value="">Mọi trạng thái</option>
            {(Object.keys(NC_STATUS_LABELS) as NcStatus[]).map((s) => (
              <option key={s} value={s}>
                {NC_STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
          <Select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as NcSeverity | '')}
            className="max-w-[160px]"
          >
            <option value="">Mọi mức độ</option>
            {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((s) => (
              <option key={s} value={s}>
                {NC_SEVERITY_LABELS[s]}
              </option>
            ))}
          </Select>
          <Select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as NcSource | '')}
            className="max-w-[200px]"
          >
            <option value="">Mọi nguồn</option>
            {(Object.keys(NC_SOURCE_LABELS) as NcSource[]).map((s) => (
              <option key={s} value={s}>
                {NC_SOURCE_LABELS[s]}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(n) => n.id}
          onRowClick={(n) => navigate(`/nonconformities/${n.id}`)}
          loading={loading}
          pageSize={12}
        />
      </Card>

      {createOpen && (
        <CreateNcModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => {
            setCreateOpen(false);
            navigate(`/nonconformities/${id}`);
          }}
        />
      )}
      {cronOpen && <RunCronModal onClose={() => setCronOpen(false)} onDone={() => { setCronOpen(false); reload(); }} />}
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: 'pending' | 'success' | 'overdue';
}) {
  const color =
    tone === 'success'
      ? 'text-success'
      : tone === 'overdue'
        ? 'text-overdue'
        : tone === 'pending'
          ? 'text-pending'
          : 'text-ink';
  return (
    <div className="rounded-xl border border-hairline bg-white px-4 py-3 shadow-card">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-subink">{label}</p>
    </div>
  );
}

function CreateNcModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState<NcSeverity>('minor');
  const [sourceType, setSourceType] = useState<NcSource>('manual');
  const [departmentId, setDepartmentId] = useState(user?.department?.id ?? '');
  const [impact, setImpact] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const canPickDept = user?.role === 'admin' || user?.role === 'leader';
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề NC');
    if (!description.trim()) return toast.error('Nhập mô tả NC');
    setSubmitting(true);
    try {
      const res = await ncApi.createNonconformity({
        title: title.trim(),
        description: description.trim(),
        severity,
        source_type: sourceType,
        department_id: canPickDept ? departmentId || undefined : undefined,
        impact_assessment: impact.trim() || null,
      });
      toast.success(`Đã tạo ${res.nc_code}`);
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
      title="Ghi nhận không phù hợp (NC)"
      description="Mã NC do hệ thống tự sinh. Sau khi tạo, Phụ trách chất lượng (QM) sẽ mở CAPA."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo phiếu NC
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tiêu đề" required className="sm:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="vd: Kết quả QC vượt giới hạn kiểm soát" />
        </Field>
        <Field label="Mô tả chi tiết" required className="sm:col-span-2">
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Mô tả sự không phù hợp…" />
        </Field>
        <Field label="Mức độ">
          <Select value={severity} onChange={(e) => setSeverity(e.target.value as NcSeverity)}>
            {(Object.keys(NC_SEVERITY_LABELS) as NcSeverity[]).map((s) => (
              <option key={s} value={s}>
                {NC_SEVERITY_LABELS[s]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Nguồn phát hiện">
          <Select value={sourceType} onChange={(e) => setSourceType(e.target.value as NcSource)}>
            {(Object.keys(NC_SOURCE_LABELS) as NcSource[]).map((s) => (
              <option key={s} value={s}>
                {NC_SOURCE_LABELS[s]}
              </option>
            ))}
          </Select>
        </Field>
        {canPickDept ? (
          <Field label="Phòng ban" className="sm:col-span-2">
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
          <Field label="Phòng ban" hint="Phiếu thuộc phòng của bạn." className="sm:col-span-2">
            <Input value={user?.department?.name ?? '—'} disabled />
          </Field>
        )}
        <Field label="Đánh giá tác động (§7.10.1)" className="sm:col-span-2" hint="Mẫu/kết quả bị ảnh hưởng, hành động tức thời…">
          <Textarea value={impact} onChange={(e) => setImpact(e.target.value)} rows={2} />
        </Field>
      </div>
    </Modal>
  );
}

function RunCronModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [asOf, setAsOf] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ncApi.RunCapaDueResult | null>(null);

  async function run() {
    setRunning(true);
    try {
      const res = await ncApi.runCapaDueCron(asOf || undefined);
      setResult(res);
      toast.success(`Đã tạo ${res.notifications_created} thông báo nhắc CAPA`);
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
      title="Nhắc CAPA tới/quá hạn (CRON-7)"
      description="Quét CAPA đang mở tới mốc 7/3/0 ngày và gửi thông báo in-app cho người phụ trách CAPA."
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
          <StatCard label="CAPA quét" value={result.scanned_capa} />
          <StatCard label="Thông báo tạo" value={result.notifications_created} />
          <StatCard label="Khử trùng lặp" value={result.deduped} />
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
