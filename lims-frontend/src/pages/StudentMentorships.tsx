import { useState } from 'react';
import { UserCog, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { canManageResearch } from '@/lib/rbac';
import type { StudentMentorship } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function StudentMentorships() {
  const { user } = useAuth();
  const toast = useToast();
  const [typeFilter, setTypeFilter] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StudentMentorship | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StudentMentorship | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => researchApi.listMentorships({ type: typeFilter || undefined, limit: 100 }),
    [typeFilter],
  );
  const { data: types } = useAsync(() => researchApi.listMentorshipTypes(), []);
  const canManage = canManageResearch(user);
  const typeLabel = (code: string) => (types ?? []).find((t) => t.code === code)?.label ?? code;

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deleteMentorship(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<StudentMentorship>[] = [
    { key: 'student', header: 'Sinh viên', sortValue: (m) => m.student_name, render: (m) => <span className="font-semibold text-ink">{m.student_name}</span> },
    { key: 'topic', header: 'Đề tài', render: (m) => m.topic ?? '—' },
    { key: 'mentor', header: 'Người hướng dẫn', render: (m) => m.mentor_name ?? '—' },
    { key: 'type', header: 'Loại', render: (m) => typeLabel(m.type) },
    { key: 'year', header: 'Năm', align: 'center', sortValue: (m) => m.year, render: (m) => m.year },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (m: StudentMentorship) => (
              <div className="flex justify-end gap-1">
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(m)}>
                  <Pencil size={14} />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(m)}>
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
        title="Hướng dẫn sinh viên"
        description="Khóa luận, luận văn, luận án và NCKH sinh viên"
        icon={<UserCog size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm
            </Button>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="max-w-[220px]">
            <option value="">Mọi loại</option>
            {(types ?? []).map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(m) => m.id} loading={loading} pageSize={12} />
      </Card>

      {createOpen && (
        <MentorshipModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm');
          }}
        />
      )}
      {editTarget && (
        <MentorshipModal
          mentorship={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
            toast.success('Đã cập nhật');
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa hướng dẫn SV"
        message={`Xóa bản ghi của sinh viên "${deleteTarget?.student_name}"?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function MentorshipModal({
  mentorship,
  onClose,
  onSaved,
}: {
  mentorship?: StudentMentorship;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const editing = !!mentorship;
  const [mentorId, setMentorId] = useState(mentorship?.mentor_id ?? user?.id ?? '');
  const [studentName, setStudentName] = useState(mentorship?.student_name ?? '');
  const [topic, setTopic] = useState(mentorship?.topic ?? '');
  const [year, setYear] = useState(String(mentorship?.year ?? new Date().getFullYear()));
  const [type, setType] = useState(mentorship?.type ?? '');
  const [submitting, setSubmitting] = useState(false);

  const { data: types } = useAsync(() => researchApi.listMentorshipTypes(), []);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  // Staff chỉ được khai cho chính mình → khóa selector mentor
  const isStaff = user?.role === 'staff';

  async function submit() {
    if (!studentName.trim()) return toast.error('Nhập tên sinh viên');
    if (!type) return toast.error('Chọn loại hướng dẫn');
    if (!editing && !mentorId) return toast.error('Chọn người hướng dẫn');
    const y = Number(year);
    if (!Number.isInteger(y)) return toast.error('Năm không hợp lệ');
    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateMentorship(mentorship!.id, {
          student_name: studentName.trim(),
          topic: topic || null,
          year: y,
          type,
        });
      } else {
        await researchApi.createMentorship({
          mentor_id: mentorId,
          student_name: studentName.trim(),
          topic: topic || null,
          year: y,
          type,
        });
      }
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
      title={editing ? 'Sửa hướng dẫn SV' : 'Thêm hướng dẫn SV'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            {editing ? 'Lưu' : 'Thêm'}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {!editing && (
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
        )}
        <Field label="Tên sinh viên" required>
          <Input value={studentName} onChange={(e) => setStudentName(e.target.value)} />
        </Field>
        <Field label="Loại hướng dẫn" required>
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">— Chọn —</option>
            {(types ?? []).map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Đề tài" className="sm:col-span-2">
          <Input value={topic} onChange={(e) => setTopic(e.target.value)} />
        </Field>
        <Field label="Năm" required>
          <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
