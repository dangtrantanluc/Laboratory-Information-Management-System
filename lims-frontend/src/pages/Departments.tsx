import { useState } from 'react';
import { Building2, Plus, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import type { Department, UserListItem } from '@/types';
import * as usersApi from '@/api/users';

export function Departments() {
  const toast = useToast();
  const [editing, setEditing] = useState<Department | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [delDept, setDelDept] = useState<Department | null>(null);

  const { data, loading, reload } = useAsync(() => usersApi.listDepartments(true), []);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100, status: 'active' }), []);

  const columns: Column<Department>[] = [
    { key: 'name', header: 'Tên phòng', sortValue: (d) => d.name, render: (d) => <span className="font-semibold text-ink">{d.name}</span> },
    { key: 'code', header: 'Mã', render: (d) => d.code },
    { key: 'lead', header: 'Trưởng nhóm', render: (d) => d.lead_user_name ?? '—' },
    { key: 'member_count', header: 'Số thành viên', align: 'center', render: (d) => d.member_count ?? 0 },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (d) => (
        <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="ghost" onClick={() => setDelDept(d)} title="Xóa">
            <Trash2 size={14} className="text-overdue" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Phòng ban"
        description="Cơ cấu phòng ban & gán trưởng nhóm"
        icon={<Building2 size={20} />}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Thêm phòng ban
          </Button>
        }
      />
      <Card>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(d) => d.id}
          loading={loading}
          pageSize={12}
          onRowClick={(d) => setEditing(d)}
        />
      </Card>

      {(createOpen || editing) && (
        <DepartmentModal
          dept={editing}
          users={users?.data ?? []}
          onClose={() => {
            setCreateOpen(false);
            setEditing(null);
          }}
          onDone={() => {
            setCreateOpen(false);
            setEditing(null);
            reload();
            toast.success('Đã lưu phòng ban');
          }}
        />
      )}

      <ConfirmDialog
        open={!!delDept}
        onClose={() => setDelDept(null)}
        title="Xóa phòng ban"
        message={`Xác nhận xóa phòng ${delDept?.name}? (Phòng sẽ chuyển sang ngừng hoạt động.)`}
        confirmText="Xóa"
        onConfirm={async () => {
          if (!delDept) return;
          try {
            await usersApi.deleteDepartment(delDept.id);
            toast.success('Đã xóa phòng ban');
            setDelDept(null);
            reload();
          } catch (err) {
            toast.error(describeError(err).title);
          }
        }}
      />
    </div>
  );
}

function DepartmentModal({
  dept,
  users,
  onClose,
  onDone,
}: {
  dept: Department | null;
  users: UserListItem[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(dept?.name ?? '');
  const [code, setCode] = useState(dept?.code ?? '');
  const [leadId, setLeadId] = useState(dept?.lead_user_id ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!name.trim()) return toast.error('Nhập tên phòng');
    if (!code.trim()) return toast.error('Nhập mã phòng');
    setSubmitting(true);
    try {
      const body = { name: name.trim(), code: code.trim(), lead_user_id: leadId || null };
      if (dept) await usersApi.updateDepartment(dept.id, body);
      else await usersApi.createDepartment(body);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  const candidates = users.filter((u) => !dept || u.department_id === dept.id || !u.department_id);

  return (
    <Modal
      open
      onClose={onClose}
      title={dept ? 'Sửa phòng ban' : 'Thêm phòng ban'}
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
      <div className="flex flex-col gap-4">
        <Field label="Tên phòng" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Mã phòng" required>
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="vd: LAB-HOA" />
        </Field>
        <Field label="Trưởng nhóm" hint="Trưởng nhóm có quyền phân công / duyệt / chốt mẫu">
          <Select value={leadId} onChange={(e) => setLeadId(e.target.value)}>
            <option value="">— Không chọn —</option>
            {(dept ? candidates : users).map((u) => (
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
