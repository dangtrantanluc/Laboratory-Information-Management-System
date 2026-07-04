import { useState } from 'react';
import { Users as UsersIcon, Plus, KeyRound, Power } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { ROLE_OPTIONS } from '@/lib/rbac';
import { ROLE_LABELS, type UserListItem } from '@/types';
import * as usersApi from '@/api/users';

export function UsersPage() {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [role, setRole] = useState('');
  const [editing, setEditing] = useState<UserListItem | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [toggleUser, setToggleUser] = useState<UserListItem | null>(null);
  const [resetUser, setResetUser] = useState<UserListItem | null>(null);

  const { data, loading, reload } = useAsync(
    () => usersApi.listUsers({ q: q || undefined, role: role || undefined, limit: 100 }),
    [q, role],
  );
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  const columns: Column<UserListItem>[] = [
    {
      key: 'full_name',
      header: 'Họ tên',
      sortValue: (u) => u.full_name,
      render: (u) => (
        <div>
          <p className="font-semibold text-ink">
            {u.full_name}
            {u.is_dept_lead && <Badge tone="info" className="ml-2">Trưởng nhóm</Badge>}
          </p>
          <p className="text-xs text-subink">{u.email}</p>
        </div>
      ),
    },
    { key: 'role', header: 'Vai trò', render: (u) => ROLE_LABELS[u.role] },
    { key: 'department_name', header: 'Phòng', render: (u) => u.department_name ?? '—' },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (u) => (
        <Badge tone={u.status === 'active' ? 'success' : 'muted'}>
          {u.status === 'active' ? 'Hoạt động' : 'Vô hiệu'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (u) => (
        <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="ghost" onClick={() => setResetUser(u)} title="Đặt lại mật khẩu">
            <KeyRound size={14} />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setToggleUser(u)}
            title={u.status === 'active' ? 'Vô hiệu hóa' : 'Kích hoạt'}
          >
            <Power size={14} className={u.status === 'active' ? 'text-overdue' : 'text-success'} />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Nhân sự"
        description="Quản lý tài khoản người dùng & phân quyền"
        icon={<UsersIcon size={20} />}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Thêm người dùng
          </Button>
        }
      />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tên / email…" className="max-w-xs flex-1" />
          <Select value={role} onChange={(e) => setRole(e.target.value)} className="max-w-[180px]">
            <option value="">Mọi vai trò</option>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(u) => u.id}
          loading={loading}
          pageSize={12}
          onRowClick={(u) => setEditing(u)}
        />
      </Card>

      {(createOpen || editing) && (
        <UserModal
          user={editing}
          depts={depts?.data ?? []}
          onClose={() => {
            setCreateOpen(false);
            setEditing(null);
          }}
          onDone={() => {
            setCreateOpen(false);
            setEditing(null);
            reload();
            toast.success('Đã lưu người dùng');
          }}
        />
      )}

      <ConfirmDialog
        open={!!toggleUser}
        onClose={() => setToggleUser(null)}
        title={toggleUser?.status === 'active' ? 'Vô hiệu hóa tài khoản' : 'Kích hoạt tài khoản'}
        message={`Xác nhận ${toggleUser?.status === 'active' ? 'vô hiệu hóa' : 'kích hoạt'} tài khoản ${toggleUser?.full_name}?`}
        tone="primary"
        confirmText="Xác nhận"
        onConfirm={async () => {
          if (!toggleUser) return;
          try {
            if (toggleUser.status === 'active') await usersApi.disableUser(toggleUser.id);
            else await usersApi.enableUser(toggleUser.id);
            toast.success('Đã cập nhật');
            setToggleUser(null);
            reload();
          } catch (err) {
            toast.error(describeError(err).title);
          }
        }}
      />

      {resetUser && (
        <ResetPasswordModal
          user={resetUser}
          onClose={() => setResetUser(null)}
          onDone={() => {
            setResetUser(null);
            toast.success('Đã đặt lại mật khẩu (người dùng phải đổi ở lần đăng nhập kế)');
          }}
        />
      )}
    </div>
  );
}

function UserModal({
  user,
  depts,
  onClose,
  onDone,
}: {
  user: UserListItem | null;
  depts: { id: string; name: string }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [role, setRole] = useState(user?.role ?? 'staff');
  const [departmentId, setDepartmentId] = useState(user?.department_id ?? '');
  const [isLead, setIsLead] = useState(user?.is_dept_lead ?? false);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!fullName.trim()) return toast.error('Nhập họ tên');
    if (!user && !email.trim()) return toast.error('Nhập email');
    setSubmitting(true);
    try {
      if (user) {
        await usersApi.updateUser(user.id, {
          full_name: fullName.trim(),
          role,
          department_id: departmentId || null,
          email: email.trim(),
        });
      } else {
        await usersApi.createUser({
          full_name: fullName.trim(),
          email: email.trim(),
          role,
          department_id: departmentId || null,
          is_dept_lead: isLead,
        });
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
      title={user ? 'Sửa người dùng' : 'Thêm người dùng'}
      description={user ? undefined : 'Mật khẩu tạm sẽ được sinh; người dùng đổi ở lần đăng nhập đầu.'}
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
        <Field label="Họ tên" required className="sm:col-span-2">
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        <Field label="Email" required className="sm:col-span-2">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Vai trò" required>
          <Select value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Phòng ban">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">— Không chọn —</option>
            {depts.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>
        {!user && (
          <label className="sm:col-span-2 flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={isLead} onChange={(e) => setIsLead(e.target.checked)} />
            Là trưởng nhóm phòng (được phân công / duyệt / chốt mẫu)
          </label>
        )}
      </div>
    </Modal>
  );
}

function ResetPasswordModal({
  user,
  onClose,
  onDone,
}: {
  user: UserListItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [pwd, setPwd] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await usersApi.resetPassword(user.id, pwd || undefined);
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
      title={`Đặt lại mật khẩu — ${user.full_name}`}
      description="Bỏ trống để hệ thống sinh mật khẩu tạm (bàn giao qua kênh an toàn)."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Đặt lại
          </Button>
        </>
      }
    >
      <Field label="Mật khẩu mới (tùy chọn)" hint="Tối thiểu 8 ký tự nếu nhập">
        <Input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} />
      </Field>
    </Modal>
  );
}
