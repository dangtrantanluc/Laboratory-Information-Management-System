import { useState } from 'react';
import { HeartHandshake, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Textarea, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canManageResearch } from '@/lib/rbac';
import type { CommunityService } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function CommunityServices() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<CommunityService | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<CommunityService | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(() => researchApi.listCommunity({ limit: 100 }), []);
  const canManage = canManageResearch(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deleteCommunity(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<CommunityService>[] = [
    { key: 'content', header: 'Hoạt động', render: (c) => <span className="font-medium text-ink">{c.content}</span> },
    { key: 'host', header: 'Đơn vị chủ trì', render: (c) => c.host ?? '—' },
    { key: 'performer', header: 'Người thực hiện', render: (c) => c.performer_name ?? '—' },
    {
      key: 'performed_at',
      header: 'Thời gian',
      sortValue: (c) => c.performed_at,
      render: (c) => formatDate(c.performed_at),
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: CommunityService) => (
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
        title="Phục vụ cộng đồng"
        description="Các hoạt động phục vụ cộng đồng, xã hội"
        icon={<HeartHandshake size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm hoạt động
            </Button>
          )
        }
      />
      <Card>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(c) => c.id} loading={loading} pageSize={12} />
      </Card>

      {createOpen && (
        <CommunityModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm');
          }}
        />
      )}
      {editTarget && (
        <CommunityModal
          service={editTarget}
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
        title="Xóa hoạt động"
        message="Xóa hoạt động cộng đồng này?"
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function CommunityModal({
  service,
  onClose,
  onSaved,
}: {
  service?: CommunityService;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const editing = !!service;
  const [performerId, setPerformerId] = useState(service?.performer_user_id ?? user?.id ?? '');
  const [content, setContent] = useState(service?.content ?? '');
  const [performedAt, setPerformedAt] = useState(service?.performed_at ?? '');
  const [host, setHost] = useState(service?.host ?? '');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const isStaff = user?.role === 'staff';

  async function submit() {
    if (!content.trim()) return toast.error('Nhập nội dung hoạt động');
    if (!performedAt) return toast.error('Chọn thời gian thực hiện');
    if (!editing && !performerId) return toast.error('Chọn người thực hiện');
    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateCommunity(service!.id, {
          content: content.trim(),
          performed_at: performedAt,
          host: host || null,
        });
      } else {
        await researchApi.createCommunity({
          content: content.trim(),
          performed_at: performedAt,
          host: host || null,
          performer_user_id: performerId,
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
      title={editing ? 'Sửa hoạt động cộng đồng' : 'Thêm hoạt động cộng đồng'}
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
          <Field label="Người thực hiện" required className="sm:col-span-2">
            <Select value={performerId} onChange={(e) => setPerformerId(e.target.value)} disabled={isStaff}>
              <option value="">— Chọn —</option>
              {(users?.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Nội dung" required className="sm:col-span-2">
          <Textarea value={content} onChange={(e) => setContent(e.target.value)} />
        </Field>
        <Field label="Thời gian" required>
          <Input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} />
        </Field>
        <Field label="Đơn vị chủ trì">
          <Input value={host} onChange={(e) => setHost(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
