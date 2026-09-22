import { useState } from 'react';
import { ErrorState } from '@/components/ui/States';
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
import { useDebounced } from '@/lib/useDebounced';
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
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [departmentId, setDepartmentId] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () =>
      hrApi.listProfiles({
        q: dq || undefined,
        department_id: departmentId || undefined,
        limit: 100,
      }),
    [dq, departmentId],
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
          <SearchInput value={q} onChange={setQ} placeholder="Tên hoặc email…" className="w-full sm:max-w-xs sm:flex-1" />
          <Select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="w-full sm:max-w-[220px]"
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
          rowKey={(p) => p.id}
          empty={error ? <ErrorState error={error} onRetry={reload} /> : undefined}
          loading={loading}
          pageSize={12}
          onRowClick={(p) => navigate(`/hr/${p.id}`)}
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
  // m48 — tên là bắt buộc, tài khoản là TUỲ CHỌN: phần lớn người trong sổ nhân sự
  // chưa có tài khoản, và ép chọn tài khoản chính là thứ làm bế tắc đợt nhập danh sách.
  const [fullName, setFullName] = useState('');
  const [birthYear, setBirthYear] = useState('');
  const [userId, setUserId] = useState('');
  // m49 — phòng công tác là dữ liệu của hồ sơ, nên chọn được ngay cả khi không gắn
  // tài khoản; trước đó phòng ban chỉ tới được qua tài khoản.
  const [deptId, setDeptId] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [hiredDate, setHiredDate] = useState('');
  const [phone, setPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // Liệt kê user để chọn gắn 1-1 (BE từ chối nếu user đã có hồ sơ)
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!fullName.trim()) return toast.error('Nhập họ và tên');
    if (!jobTitle.trim()) return toast.error('Nhập chức danh');
    const by = birthYear.trim() ? Number(birthYear) : null;
    if (by !== null && (!Number.isInteger(by) || by < 1900 || by > 2100)) {
      return toast.error('Năm sinh không hợp lệ');
    }
    setSubmitting(true);
    try {
      await hrApi.createProfile({
        full_name: fullName.trim(),
        birth_year: by,
        user_id: userId || null,
        department_id: deptId || null,
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
      description="Hồ sơ mô tả con người. Tài khoản đăng nhập là tuỳ chọn — gắn ngay hoặc gắn sau."
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
        <Field label="Họ và tên" required>
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        <Field label="Năm sinh">
          <Input
            value={birthYear}
            onChange={(e) => setBirthYear(e.target.value)}
            inputMode="numeric"
            placeholder="1990"
          />
        </Field>
        <Field
          label="Tài khoản đăng nhập"
          className="md:col-span-2"
          hint="Bỏ trống nếu người này chưa có tài khoản — gắn sau ở màn hình chi tiết"
        >
          <Select value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">— Chưa có tài khoản —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Phòng công tác" hint="Để trống nếu chưa xếp phòng">
          <Select value={deptId} onChange={(e) => setDeptId(e.target.value)}>
            <option value="">— Chưa xếp phòng —</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
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
        <Field label="Số điện thoại" className="md:col-span-2">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="09xx…" />
        </Field>
      </div>
    </Modal>
  );
}
