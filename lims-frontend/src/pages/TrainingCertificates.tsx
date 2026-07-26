import { useState } from 'react';
import { Award, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Field, Input, Textarea } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import type { TrainingCertificate } from '@/types';
import { canManageActivities } from '@/lib/rbac';
import * as activityApi from '@/api/activity';


export function TrainingCertificates() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TrainingCertificate | null>(null);
  const [viewTarget, setViewTarget] = useState<TrainingCertificate | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TrainingCertificate | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(() => activityApi.listCertificates({ limit: 100 }), []);
  const canManage = canManageActivities(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await activityApi.deleteCertificate(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<TrainingCertificate>[] = [
    { key: 'recipient', header: 'Người được cấp', render: (c) => <span className="font-medium text-ink">{c.recipient_name}</span> },
    { key: 'cert_no', priority: 1, header: 'Số GCN', render: (c) => c.certificate_no ?? '—' },
    { key: 'course', header: 'Lớp học / khóa', render: (c) => c.course_name ?? '—' },
    { key: 'issued', priority: 1, header: 'Ngày cấp', sortValue: (c) => c.issued_date ?? '', render: (c) => (c.issued_date ? formatDate(c.issued_date) : '—') },
    { key: 'year', header: 'Năm học', render: (c) => c.academic_year ?? '—' },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: TrainingCertificate) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(c)}><Pencil size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(c)}><Trash2 size={14} className="text-overdue" /></Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Chứng nhận đào tạo"
        description="Danh sách học viên lớp ngắn hạn được cấp giấy chứng nhận (GCN)"
        icon={<Award size={20} />}
        actions={canManage && <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Thêm chứng nhận</Button>}
      />
      <Card>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(c) => c.id} loading={loading} pageSize={12} onRowClick={(c) => setViewTarget(c)} />
      </Card>

      {createOpen && <CertModal onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); reload(); toast.success('Đã thêm'); }} />}
      {editTarget && <CertModal cert={editTarget} onClose={() => setEditTarget(null)} onSaved={() => { setEditTarget(null); reload(); toast.success('Đã cập nhật'); }} />}
      {viewTarget && (
        <Modal open onClose={() => setViewTarget(null)} title="Chi tiết chứng nhận" footer={<><Button variant="secondary" onClick={() => setViewTarget(null)}>Đóng</Button>{canManage && <Button onClick={() => { const c = viewTarget; setViewTarget(null); setEditTarget(c); }}><Pencil size={14} /> Chỉnh sửa</Button>}</>}>
          <DescList>
            <DescItem label="Người được cấp" value={viewTarget.recipient_name} />
            <DescItem label="Số GCN" value={viewTarget.certificate_no} />
            <DescItem label="Lớp học / khóa" value={viewTarget.course_name} />
            <DescItem label="Ngày cấp" value={viewTarget.issued_date ? formatDate(viewTarget.issued_date) : '—'} />
            <DescItem label="Năm học" value={viewTarget.academic_year} />
            <DescItem full label="Ghi chú" value={viewTarget.note} />
          </DescList>
        </Modal>
      )}
      <ConfirmDialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={doDelete} title="Xóa chứng nhận" message="Xóa chứng nhận này?" confirmText="Xóa" loading={deleting} />
    </div>
  );
}

function CertModal({ cert, onClose, onSaved }: { cert?: TrainingCertificate; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const editing = !!cert;
  const [recipient, setRecipient] = useState(cert?.recipient_name ?? '');
  const [certNo, setCertNo] = useState(cert?.certificate_no ?? '');
  const [course, setCourse] = useState(cert?.course_name ?? '');
  const [issuedDate, setIssuedDate] = useState(cert?.issued_date ?? '');
  const [academicYear, setAcademicYear] = useState(cert?.academic_year ?? '');
  const [note, setNote] = useState(cert?.note ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!recipient.trim()) return toast.error('Nhập tên người được cấp');
    setSubmitting(true);
    try {
      const body = { recipient_name: recipient.trim(), certificate_no: certNo || null, course_name: course || null, issued_date: issuedDate || null, academic_year: academicYear || null, note: note || null };
      if (editing) await activityApi.updateCertificate(cert!.id, body);
      else await activityApi.createCertificate(body);
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={editing ? 'Sửa chứng nhận' : 'Thêm chứng nhận'} footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button onClick={submit} loading={submitting}>{editing ? 'Lưu' : 'Thêm'}</Button></>}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Người được cấp GCN" required className="md:col-span-2"><Input value={recipient} onChange={(e) => setRecipient(e.target.value)} /></Field>
        <Field label="Số GCN"><Input value={certNo} onChange={(e) => setCertNo(e.target.value)} /></Field>
        <Field label="Ngày cấp"><Input type="date" value={issuedDate ?? ''} onChange={(e) => setIssuedDate(e.target.value)} /></Field>
        <Field label="Lớp học / khóa"><Input value={course} onChange={(e) => setCourse(e.target.value)} /></Field>
        <Field label="Năm học"><Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" /></Field>
        <Field label="Ghi chú" className="md:col-span-2"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
