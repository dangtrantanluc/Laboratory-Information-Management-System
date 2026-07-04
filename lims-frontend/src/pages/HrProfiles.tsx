import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Plus, AlertTriangle } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatMoney, daysUntil } from '@/lib/format';
import { canManageHr } from '@/lib/rbac';
import type { HrProfile } from '@/types';
import * as hrApi from '@/api/hr';
import * as usersApi from '@/api/users';

/** Badge cảnh báo cho ngày tới hạn (HĐ hết hạn / nâng lương). */
function DueDateCell({ iso, warnWithin = 30 }: { iso?: string | null; warnWithin?: number }) {
  if (!iso) return <span className="text-subink">—</span>;
  const days = daysUntil(iso);
  const tone = days < 0 ? 'overdue' : days <= warnWithin ? 'warning' : 'neutral';
  return (
    <Badge tone={tone}>
      {tone !== 'neutral' && <AlertTriangle size={12} />}
      {formatDate(iso)}
      {days >= 0 && days <= warnWithin ? ` (còn ${days}n)` : days < 0 ? ' (quá hạn)' : ''}
    </Badge>
  );
}

export function HrProfiles() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () =>
      hrApi.listProfiles({
        q: q || undefined,
        department_id: departmentId || undefined,
        limit: 100,
      }),
    [q, departmentId],
  );
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  const columns: Column<HrProfile>[] = [
    {
      key: 'full_name',
      header: 'Nhân sự',
      sortValue: (p) => p.full_name,
      render: (p) => (
        <div>
          <p className="font-semibold text-ink">{p.full_name}</p>
          {p.email && <p className="text-xs text-subink">{p.email}</p>}
        </div>
      ),
    },
    { key: 'department_name', header: 'Phòng', render: (p) => p.department_name ?? '—' },
    { key: 'job_title', header: 'Chức danh', render: (p) => p.job_title ?? '—' },
    {
      key: 'salary',
      header: 'Lương thực nhận',
      align: 'right',
      // Lương VẮNG MẶT khi không đủ quyền → hiển thị "—" (không strip lỗi)
      render: (p) =>
        'computed_salary_amount' in p ? (
          <span className="font-medium">{formatMoney(p.computed_salary_amount, p.currency ?? 'VND')}</span>
        ) : (
          <span className="text-subink">—</span>
        ),
    },
    {
      key: 'contract_end',
      header: 'HĐ hết hạn',
      render: (p) =>
        'contract_end_date' in p ? <DueDateCell iso={p.contract_end_date} warnWithin={30} /> : '—',
    },
    {
      key: 'next_raise',
      header: 'Nâng lương kế tiếp',
      render: (p) =>
        'next_salary_raise_date' in p ? (
          <DueDateCell iso={p.next_salary_raise_date} warnWithin={15} />
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Nhân sự"
        description="Hồ sơ nhân sự, hợp đồng, lương và hồ sơ năng lực"
        icon={<Users size={20} />}
        actions={
          canManageHr(user) && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm hồ sơ
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tên hoặc email…" className="max-w-xs flex-1" />
          <Select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="max-w-[220px]"
          >
            <option value="">Mọi phòng ban</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(p) => p.user_id}
          loading={loading}
          pageSize={12}
          onRowClick={(p) => navigate(`/hr/${p.user_id}`)}
        />
      </Card>

      {createOpen && (
        <CreateProfileModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã tạo hồ sơ nhân sự');
          }}
        />
      )}
    </div>
  );
}

function CreateProfileModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const toast = useToast();
  const [userId, setUserId] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [hiredDate, setHiredDate] = useState('');
  const [phone, setPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // Liệt kê user để chọn gắn 1-1 (BE từ chối nếu user đã có hồ sơ)
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);

  async function submit() {
    if (!userId) return toast.error('Chọn người dùng');
    if (!jobTitle.trim()) return toast.error('Nhập chức danh');
    setSubmitting(true);
    try {
      await hrApi.createProfile({
        user_id: userId,
        job_title: jobTitle.trim(),
        hired_date: hiredDate || null,
        phone: phone || null,
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
      title="Thêm hồ sơ nhân sự"
      description="Gắn hồ sơ với một tài khoản người dùng (1-1). Lương ghi nhận sau khi tạo hồ sơ."
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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Người dùng" required className="sm:col-span-2">
          <Select value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">— Chọn người dùng —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Chức danh" required>
          <Input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="KTV chính" />
        </Field>
        <Field label="Ngày vào làm">
          <Input type="date" value={hiredDate} onChange={(e) => setHiredDate(e.target.value)} />
        </Field>
        <Field label="Số điện thoại" className="sm:col-span-2">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="09xx…" />
        </Field>
      </div>
    </Modal>
  );
}
