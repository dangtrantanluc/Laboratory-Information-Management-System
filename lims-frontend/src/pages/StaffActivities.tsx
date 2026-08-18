import { useState } from 'react';
import { Landmark, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Field, Input, Textarea, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { STAFF_ACTIVITY_KIND_LABELS } from '@/types';
import type { StaffActivity, StaffActivityKind } from '@/types';
import { canManageActivities } from '@/lib/rbac';
import * as activityApi from '@/api/activity';

const KINDS: StaffActivityKind[] = ['dang', 'cong_doan', 'vilas', 'khac'];


export function StaffActivities() {
  const { user } = useAuth();
  const toast = useToast();
  const [kindFilter, setKindFilter] = useState<StaffActivityKind | ''>('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StaffActivity | null>(null);
  const [viewTarget, setViewTarget] = useState<StaffActivity | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StaffActivity | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => activityApi.listActivities({ limit: 100, kind: kindFilter || undefined }),
    [kindFilter],
  );
  const canManage = canManageActivities(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await activityApi.deleteActivity(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<StaffActivity>[] = [
    { key: 'kind', header: 'Nhóm', render: (a) => STAFF_ACTIVITY_KIND_LABELS[a.kind] },
    { key: 'content', header: 'Hoạt động', render: (a) => <span className="font-medium text-ink">{a.content}</span> },
    { key: 'performer', header: 'Người thực hiện', render: (a) => a.performer_name ?? '—' },
    { key: 'year', header: 'Năm học', render: (a) => a.academic_year ?? '—' },
    {
      key: 'evidence',
      header: 'Minh chứng',
      align: 'center',
      render: (a) =>
        a.evidence_url ? (
          <a href={a.evidence_url} target="_blank" rel="noreferrer" className="text-berry hover:underline" onClick={(e) => e.stopPropagation()}>
            Xem
          </a>
        ) : (
          '—'
        ),
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (a: StaffActivity) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(a)}><Pencil size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(a)}><Trash2 size={14} className="text-overdue" /></Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Công tác khác"
        description="Công tác Đảng / Công đoàn / VILAS và các hoạt động khác"
        icon={<Landmark size={20} />}
        actions={canManage && <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Thêm hoạt động</Button>}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <span className="text-sm text-subink">Nhóm:</span>
          <Select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as StaffActivityKind | '')}
            className="w-full sm:max-w-[220px]"
          >
            <option value="">Tất cả</option>
            {KINDS.map((k) => <option key={k} value={k}>{STAFF_ACTIVITY_KIND_LABELS[k]}</option>)}
          </Select>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(a) => a.id} loading={loading} pageSize={12} onRowClick={(a) => setViewTarget(a)} />
      </Card>

      {createOpen && <ActivityModal onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); reload(); toast.success('Đã thêm'); }} />}
      {editTarget && <ActivityModal activity={editTarget} onClose={() => setEditTarget(null)} onSaved={() => { setEditTarget(null); reload(); toast.success('Đã cập nhật'); }} />}
      {viewTarget && (
        <Modal open onClose={() => setViewTarget(null)} title="Chi tiết hoạt động" footer={<><Button variant="secondary" onClick={() => setViewTarget(null)}>Đóng</Button>{canManage && <Button onClick={() => { const a = viewTarget; setViewTarget(null); setEditTarget(a); }}><Pencil size={14} /> Chỉnh sửa</Button>}</>}>
          <DescList>
            <DescItem label="Nhóm" value={STAFF_ACTIVITY_KIND_LABELS[viewTarget.kind]} />
            <DescItem label="Người thực hiện" value={viewTarget.performer_name} />
            <DescItem full label="Nội dung" value={<span className="whitespace-pre-wrap">{viewTarget.content}</span>} />
            <DescItem label="Thời gian" value={viewTarget.performed_at ? formatDate(viewTarget.performed_at) : '—'} />
            <DescItem label="Năm học" value={viewTarget.academic_year} />
          </DescList>
        </Modal>
      )}
      <ConfirmDialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={doDelete} title="Xóa hoạt động" message="Xóa hoạt động này?" confirmText="Xóa" loading={deleting} />
    </div>
  );
}

function ActivityModal({ activity, onClose, onSaved }: { activity?: StaffActivity; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const editing = !!activity;
  const [kind, setKind] = useState<StaffActivityKind>(activity?.kind ?? 'dang');
  const [content, setContent] = useState(activity?.content ?? '');
  const [performedAt, setPerformedAt] = useState(activity?.performed_at ?? '');
  const [academicYear, setAcademicYear] = useState(activity?.academic_year ?? '');
  const [evidenceUrl, setEvidenceUrl] = useState(activity?.evidence_url ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!content.trim()) return toast.error('Nhập nội dung hoạt động');
    setSubmitting(true);
    const body = {
      kind,
      content: content.trim(),
      performed_at: performedAt || null,
      academic_year: academicYear || null,
      evidence_url: evidenceUrl.trim() || null,
    };
    try {
      if (editing) await activityApi.updateActivity(activity!.id, body);
      else await activityApi.createActivity(body);
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={editing ? 'Sửa hoạt động' : 'Thêm hoạt động'} footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button onClick={submit} loading={submitting}>{editing ? 'Lưu' : 'Thêm'}</Button></>}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Nhóm công tác" required>
          <Select value={kind} onChange={(e) => setKind(e.target.value as StaffActivityKind)}>
            {KINDS.map((k) => <option key={k} value={k}>{STAFF_ACTIVITY_KIND_LABELS[k]}</option>)}
          </Select>
        </Field>
        <Field label="Năm học"><Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" /></Field>
        <Field label="Nội dung hoạt động" required className="md:col-span-2"><Textarea rows={3} value={content} onChange={(e) => setContent(e.target.value)} /></Field>
        <Field label="Thời gian"><Input type="date" value={performedAt ?? ''} onChange={(e) => setPerformedAt(e.target.value)} /></Field>
        <Field label="Link minh chứng" hint="Hình ảnh, khen thưởng, quyết định, chứng nhận"><Input value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} placeholder="https://" /></Field>
      </div>
    </Modal>
  );
}
