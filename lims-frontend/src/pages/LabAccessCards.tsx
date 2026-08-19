import { useState } from 'react';
import { CreditCard, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Textarea } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canManageLabAccessCards } from '@/lib/rbac';
import type { LabAccessCard } from '@/types';
import * as labAccessApi from '@/api/labAccess';

export function LabAccessCards() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [supervisorName, setSupervisorName] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<LabAccessCard | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LabAccessCard | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () =>
      labAccessApi.listLabAccessCards({
        q: dq || undefined,
        supervisor_name: supervisorName || undefined,
        limit: 100,
      }),
    [dq, supervisorName],
  );
  const canManage = canManageLabAccessCards(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await labAccessApi.deleteLabAccessCard(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<LabAccessCard>[] = [
    { key: 'stt', header: 'STT', align: 'center', render: (_c, i) => i + 1 },
    {
      key: 'student',
      header: 'Sinh viên',
      sortValue: (c) => c.student_name,
      render: (c) => (
        <div>
          <p className="font-semibold text-ink">{c.student_name}</p>
          <p className="text-xs text-subink">
            {c.class_name ?? '—'} · {c.student_code}
          </p>
        </div>
      ),
    },
    { key: 'email', header: 'Email', render: (c) => c.email ?? '—' },
    { key: 'room', header: 'Phòng đăng ký', render: (c) => c.room },
    { key: 'purpose', header: 'Mục đích', render: (c) => c.purpose ?? '—' },
    { key: 'supervisor', header: 'Giáo viên hướng dẫn', render: (c) => c.supervisor_name ?? '—' },
    {
      key: 'period',
      header: 'Thời gian',
      render: (c) => `${formatDate(c.valid_from)} → ${c.valid_to ? formatDate(c.valid_to) : '—'}`,
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: LabAccessCard) => (
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
        title="Thẻ vào PTN"
        description="Danh sách sinh viên được cấp thẻ vào phòng thí nghiệm — Văn phòng quản lý"
        icon={<CreditCard size={20} />}
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
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm tên / MSSV / lớp / email"
            className="w-full sm:max-w-[260px]"
          />
          <Input
            value={supervisorName}
            onChange={(e) => setSupervisorName(e.target.value)}
            placeholder="Lọc theo giáo viên hướng dẫn"
            className="w-full sm:max-w-[260px]"
          />
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(c) => c.id} loading={loading} pageSize={12} />
      </Card>

      {createOpen && (
        <CardModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm');
          }}
        />
      )}
      {editTarget && (
        <CardModal
          card={editTarget}
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
        title="Xóa bản ghi thẻ vào PTN"
        message={`Xóa bản ghi của sinh viên "${deleteTarget?.student_name}"?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function CardModal({
  card,
  onClose,
  onSaved,
}: {
  card?: LabAccessCard;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!card;
  const [studentName, setStudentName] = useState(card?.student_name ?? '');
  const [className, setClassName] = useState(card?.class_name ?? '');
  const [studentCode, setStudentCode] = useState(card?.student_code ?? '');
  const [email, setEmail] = useState(card?.email ?? '');
  const [room, setRoom] = useState(card?.room ?? '');
  const [purpose, setPurpose] = useState(card?.purpose ?? '');
  const [supervisorName, setSupervisorName] = useState(card?.supervisor_name ?? '');
  const [validFrom, setValidFrom] = useState(card?.valid_from ?? '');
  const [validTo, setValidTo] = useState(card?.valid_to ?? '');
  const [note, setNote] = useState(card?.note ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!studentName.trim()) return toast.error('Nhập tên sinh viên');
    if (!studentCode.trim()) return toast.error('Nhập MSSV');
    if (!room.trim()) return toast.error('Nhập phòng đăng ký sử dụng');
    if (!validFrom) return toast.error('Chọn ngày bắt đầu');
    if (validTo && validTo < validFrom) return toast.error('Ngày kết thúc phải sau ngày bắt đầu');
    setSubmitting(true);
    try {
      const body = {
        student_name: studentName.trim(),
        class_name: className.trim() || null,
        student_code: studentCode.trim(),
        email: email.trim() || null,
        room: room.trim(),
        purpose: purpose.trim() || null,
        supervisor_name: supervisorName.trim() || null,
        valid_from: validFrom,
        valid_to: validTo || null,
        note: note.trim() || null,
      };
      if (editing) await labAccessApi.updateLabAccessCard(card!.id, body);
      else await labAccessApi.createLabAccessCard(body);
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
      size="lg"
      title={editing ? 'Sửa thẻ vào PTN' : 'Thêm thẻ vào PTN'}
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
      <FormBody>
        <FormSection title="Sinh viên">
        <Field label="Họ và tên" required>
          <Input value={studentName} onChange={(e) => setStudentName(e.target.value)} />
        </Field>
        <Field label="Lớp">
          <Input value={className} onChange={(e) => setClassName(e.target.value)} />
        </Field>
        <Field label="MSSV" required>
          <Input value={studentCode} onChange={(e) => setStudentCode(e.target.value)} />
        </Field>
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        </FormSection>

        <FormSection title="Đăng ký sử dụng">
        <Field label="Đăng ký sử dụng PTN" required>
          <Input value={room} onChange={(e) => setRoom(e.target.value)} placeholder="vd: RIBE 306" />
        </Field>
        <Field label="Mục đích sử dụng">
          <Input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="vd: Rèn nghề, KLTN" />
        </Field>
        <Field label="Giáo viên hướng dẫn" className="md:col-span-2">
          <Input value={supervisorName} onChange={(e) => setSupervisorName(e.target.value)} />
        </Field>
        </FormSection>

        <FormSection title="Hiệu lực">
        <Field label="Từ ngày" required>
          <Input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
        </Field>
        <Field label="Đến ngày">
          <Input type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />
        </Field>
        <Field label="Ghi chú" className="md:col-span-2">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}
