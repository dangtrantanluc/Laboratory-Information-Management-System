import { useState } from 'react';
import { Presentation, Plus, Pencil, Trash2 } from 'lucide-react';
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
import type { TeachingCourse } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function TeachingCourses() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TeachingCourse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TeachingCourse | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(() => researchApi.listTeaching({ limit: 100 }), []);
  const canManage = canManageResearch(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deleteTeaching(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<TeachingCourse>[] = [
    { key: 'course', header: 'Môn học', sortValue: (c) => c.course_name, render: (c) => <span className="font-semibold text-ink">{c.course_name}</span> },
    { key: 'user', header: 'Người phụ trách', render: (c) => c.user_name ?? '—' },
    { key: 'semester', header: 'Học kỳ', render: (c) => c.semester },
    { key: 'year', header: 'Năm', align: 'center', sortValue: (c) => c.year, render: (c) => c.year },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: TeachingCourse) => (
              <div className="flex justify-end gap-1">
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(c)}>
                  <Pencil size={14} />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(c)}>
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
        title="Môn giảng dạy"
        description="Các môn học được phân công giảng dạy theo học kỳ"
        icon={<Presentation size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm môn
            </Button>
          )
        }
      />
      <Card>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(c) => c.id} loading={loading} pageSize={12} />
      </Card>

      {createOpen && (
        <TeachingModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm');
          }}
        />
      )}
      {editTarget && (
        <TeachingModal
          course={editTarget}
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
        title="Xóa môn giảng dạy"
        message={`Xóa môn "${deleteTarget?.course_name}"?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function TeachingModal({
  course,
  onClose,
  onSaved,
}: {
  course?: TeachingCourse;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const editing = !!course;
  const [userId, setUserId] = useState(course?.user_id ?? user?.id ?? '');
  const [courseName, setCourseName] = useState(course?.course_name ?? '');
  const [semester, setSemester] = useState(course?.semester ?? '');
  const [year, setYear] = useState(String(course?.year ?? new Date().getFullYear()));
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const isStaff = user?.role === 'staff';

  async function submit() {
    if (!courseName.trim()) return toast.error('Nhập tên môn');
    if (!semester.trim()) return toast.error('Nhập học kỳ');
    if (!editing && !userId) return toast.error('Chọn người phụ trách');
    const y = Number(year);
    if (!Number.isInteger(y)) return toast.error('Năm không hợp lệ');
    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateTeaching(course!.id, {
          course_name: courseName.trim(),
          semester: semester.trim(),
          year: y,
        });
      } else {
        await researchApi.createTeaching({
          user_id: userId,
          course_name: courseName.trim(),
          semester: semester.trim(),
          year: y,
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
      title={editing ? 'Sửa môn giảng dạy' : 'Thêm môn giảng dạy'}
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
          <Field label="Người phụ trách" required className="sm:col-span-2">
            <Select value={userId} onChange={(e) => setUserId(e.target.value)} disabled={isStaff}>
              <option value="">— Chọn —</option>
              {(users?.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Tên môn" required className="sm:col-span-2">
          <Input value={courseName} onChange={(e) => setCourseName(e.target.value)} />
        </Field>
        <Field label="Học kỳ" required>
          <Input value={semester} onChange={(e) => setSemester(e.target.value)} placeholder="HK1" />
        </Field>
        <Field label="Năm học" required>
          <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
