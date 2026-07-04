import { useState } from 'react';
import { ClipboardCheck, Plus, Check, X } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { RegistrationStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canManageResearch } from '@/lib/rbac';
import type { LabRegistration } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function LabRegistrations() {
  const { user } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [decide, setDecide] = useState<{ reg: LabRegistration; action: 'approve' | 'reject' } | null>(null);

  const { data, loading, reload } = useAsync(
    () => researchApi.listRegistrations({ status: status || undefined, limit: 100 }),
    [status],
  );
  const canManage = canManageResearch(user);
  // Có thể quyết định: admin/leader; mentor của lượt; trưởng nhóm phòng (BE re-validate)
  const canDecide = (reg: LabRegistration) =>
    user?.role === 'admin' ||
    user?.role === 'leader' ||
    reg.mentor_id === user?.id ||
    !!user?.is_dept_lead;

  const columns: Column<LabRegistration>[] = [
    { key: 'student', header: 'Sinh viên', sortValue: (r) => r.student_name, render: (r) => <span className="font-semibold text-ink">{r.student_name}</span> },
    { key: 'mentor', header: 'Người hướng dẫn', render: (r) => r.mentor_name ?? '—' },
    { key: 'purpose', header: 'Mục đích', render: (r) => r.purpose },
    {
      key: 'period',
      header: 'Thời gian',
      render: (r) => `${formatDate(r.registered_from)} → ${r.registered_to ? formatDate(r.registered_to) : '—'}`,
    },
    { key: 'status', header: 'Trạng thái', render: (r) => <RegistrationStatusBadge status={r.status} /> },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (r) =>
        r.status === 'pending' && canDecide(r) ? (
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="success" onClick={() => setDecide({ reg: r, action: 'approve' })}>
              <Check size={14} /> Duyệt
            </Button>
            <Button size="sm" variant="danger" onClick={() => setDecide({ reg: r, action: 'reject' })}>
              <X size={14} /> Từ chối
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Đăng ký lab"
        description="Sinh viên đăng ký sử dụng phòng thí nghiệm — có duyệt"
        icon={<ClipboardCheck size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Đăng ký mới
            </Button>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-[200px]">
            <option value="">Mọi trạng thái</option>
            <option value="pending">Chờ duyệt</option>
            <option value="approved">Đã duyệt</option>
            <option value="rejected">Đã từ chối</option>
          </Select>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(r) => r.id} loading={loading} pageSize={12} />
      </Card>

      {createOpen && (
        <RegistrationModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã tạo lượt đăng ký (chờ duyệt)');
          }}
        />
      )}
      {decide && (
        <DecideModal
          registration={decide.reg}
          action={decide.action}
          onClose={() => setDecide(null)}
          onDone={() => {
            setDecide(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function RegistrationModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const [mentorId, setMentorId] = useState(user?.id ?? '');
  const [studentName, setStudentName] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [purpose, setPurpose] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const isStaff = user?.role === 'staff';

  async function submit() {
    if (!studentName.trim()) return toast.error('Nhập tên sinh viên');
    if (!mentorId) return toast.error('Chọn người hướng dẫn');
    if (!from) return toast.error('Chọn ngày bắt đầu');
    if (!purpose.trim()) return toast.error('Nhập mục đích');
    setSubmitting(true);
    try {
      await researchApi.createRegistration({
        student_name: studentName.trim(),
        mentor_id: mentorId,
        registered_from: from,
        registered_to: to || null,
        purpose: purpose.trim(),
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
      title="Đăng ký sử dụng lab"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Gửi đăng ký
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Người hướng dẫn" required className="sm:col-span-2">
          <Select value={mentorId} onChange={(e) => setMentorId(e.target.value)} disabled={isStaff}>
            <option value="">— Chọn —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Tên sinh viên" required>
          <Input value={studentName} onChange={(e) => setStudentName(e.target.value)} />
        </Field>
        <Field label="Mục đích" required>
          <Input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Thực tập dùng HPLC" />
        </Field>
        <Field label="Từ ngày" required>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="Đến ngày">
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function DecideModal({
  registration,
  action,
  onClose,
  onDone,
}: {
  registration: LabRegistration;
  action: 'approve' | 'reject';
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const approving = action === 'approve';

  async function submit() {
    setSubmitting(true);
    try {
      if (approving) await researchApi.approveRegistration(registration.id, reason || undefined);
      else await researchApi.rejectRegistration(registration.id, reason || undefined);
      toast.success(approving ? 'Đã duyệt lượt đăng ký' : 'Đã từ chối lượt đăng ký');
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
      size="sm"
      title={approving ? 'Duyệt lượt đăng ký' : 'Từ chối lượt đăng ký'}
      description={`Sinh viên: ${registration.student_name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button variant={approving ? 'success' : 'danger'} onClick={submit} loading={submitting}>
            {approving ? 'Duyệt' : 'Từ chối'}
          </Button>
        </>
      }
    >
      <Field label="Lý do" hint={approving ? 'Không bắt buộc' : 'Nên ghi rõ lý do từ chối'}>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
    </Modal>
  );
}
