import { useState } from 'react';
import { HeartHandshake, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  DescList,
  DescItem,
  DescLink,
  DescSection,
} from '@/components/ui/DescList';
import { Avatar } from '@/components/ui/Avatar';
import { Field, Input, Textarea, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, truncate } from '@/lib/format';
import { canManageResearch } from '@/lib/rbac';
import type { CommunityService } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function CommunityServices() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<CommunityService | null>(null);
  const [viewTarget, setViewTarget] = useState<CommunityService | null>(null);
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
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
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
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(c) => c.id}
          loading={loading}
          pageSize={12}
          onRowClick={(c) => setViewTarget(c)}
        />
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
      {viewTarget && (
        <CommunityDetailModal
          service={viewTarget}
          canManage={canManage}
          onClose={() => setViewTarget(null)}
          onEdit={() => {
            const c = viewTarget;
            setViewTarget(null);
            setEditTarget(c);
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa hoạt động"
        message={`Xóa hoạt động "${truncate(deleteTarget?.content)}"? Thao tác không thể hoàn tác.`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function CommunityDetailModal({
  service: c,
  canManage,
  onClose,
  onEdit,
}: {
  service: CommunityService;
  canManage: boolean;
  onClose: () => void;
  onEdit: () => void;
}) {
  const TITLE_MAX = 90;
  const truncated = c.content.length > TITLE_MAX;

  return (
    <Modal
      open
      onClose={onClose}
      // Modal này chỉ có 5 trường: giữ khổ `md`. Cho `lg` như hai modal kia sẽ
      // thành hộp rộng gần như trống — đúng lỗi "quá thưa" của bản cũ.
      title={truncate(c.content, TITLE_MAX)}
      description="Hoạt động phục vụ cộng đồng, xã hội"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Đóng
          </Button>
          {canManage && (
            <Button onClick={onEdit}>
              <Pencil size={14} /> Chỉnh sửa
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-6">
        {/* KHÔNG dùng DetailHero ở đây: bản ghi này không có con số chủ đạo hay
            trạng thái nào, nên dải tóm tắt chỉ còn một chip lẻ trong khung lớn —
            thêm khoảng trống chứ không thêm thông tin. Hero dành cho bản ghi có
            kinh phí / giá trị / trạng thái để neo mắt. */}

        {/* Chỉ hiện lại nội dung khi tiêu đề đã bị cắt — nếu không thì đây là đoạn
            chữ y hệt tiêu đề nằm ngay dưới tiêu đề. */}
        {truncated && (
          <DescSection title="Nội dung">
            <DescList cols={1}>
              <DescItem
                full
                label="Mô tả hoạt động"
                value={<span className="whitespace-pre-wrap">{c.content}</span>}
              />
            </DescList>
          </DescSection>
        )}

        <DescSection title="Thực hiện">
          <DescList>
            <DescItem label="Thời gian" value={formatDate(c.performed_at)} />
            <DescItem
              label="Người thực hiện"
              value={
                c.performer_name ? (
                  <span className="inline-flex items-center gap-2">
                    <Avatar name={c.performer_name} size="sm" />
                    {c.performer_name}
                  </span>
                ) : null
              }
            />
            <DescItem label="Đơn vị chủ trì" value={c.host} />
            <DescItem label="Phòng ban" value={c.department_name} />
            <DescLink url={c.evidence_url} />
          </DescList>
        </DescSection>
      </div>
    </Modal>
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
  const [evidenceUrl, setEvidenceUrl] = useState(service?.evidence_url ?? '');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const isStaff = user?.role === 'staff';

  async function submit() {
    if (!content.trim()) return toast.error('Nhập nội dung hoạt động');
    if (!performedAt) return toast.error('Chọn thời gian thực hiện');
    if (!editing && !performerId) return toast.error('Chọn người thực hiện');
    setSubmitting(true);
    try {
      const shared = {
        content: content.trim(),
        performed_at: performedAt,
        host: host || null,
        evidence_url: evidenceUrl.trim() || null,
      };
      if (editing) {
        await researchApi.updateCommunity(service!.id, shared);
      } else {
        await researchApi.createCommunity({ ...shared, performer_user_id: performerId });
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
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {!editing && (
          <Field label="Người thực hiện" required className="md:col-span-2">
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
        <Field label="Nội dung" required className="md:col-span-2">
          <Textarea value={content} onChange={(e) => setContent(e.target.value)} />
        </Field>
        <Field label="Thời gian" required>
          <Input type="date" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} />
        </Field>
        <Field label="Link minh chứng" className="md:col-span-2">
          <Input value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} placeholder="https://" />
        </Field>
        <Field label="Đơn vị chủ trì">
          <Input value={host} onChange={(e) => setHost(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
