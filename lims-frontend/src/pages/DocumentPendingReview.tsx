import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardCheck, Check, X, ArrowUpRight } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Textarea } from '@/components/ui/Field';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { PendingReviewItem } from '@/types';
import * as docsApi from '@/api/documents';

export function DocumentPendingReview() {
  const toast = useToast();
  const navigate = useNavigate();
  const { data, loading, reload } = useAsync(() => docsApi.listPendingReview({ limit: 100 }), []);

  const [approveTarget, setApproveTarget] = useState<PendingReviewItem | null>(null);
  const [rejectTarget, setRejectTarget] = useState<PendingReviewItem | null>(null);
  const [approving, setApproving] = useState(false);

  async function doApprove() {
    if (!approveTarget) return;
    setApproving(true);
    try {
      await docsApi.approveVersion(approveTarget.document_id, approveTarget.version_id);
      toast.success('Đã ban hành phiên bản');
      setApproveTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setApproving(false);
    }
  }

  const items = data?.data ?? [];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Phiên bản chờ duyệt"
        description="Các phiên bản tài liệu đang chờ bạn phê duyệt và ban hành"
        icon={<ClipboardCheck size={20} />}
      />

      <Card>
        <CardBody className="p-0">
          {loading ? (
            <LoadingState />
          ) : items.length === 0 ? (
            <EmptyState title="Không có phiên bản chờ duyệt" description="Mọi tài liệu trong phạm vi của bạn đã được xử lý." />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {items.map((it) => (
                <li
                  key={it.version_id}
                  className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">
                      {it.title} <span className="text-subink">· v{it.version_no}</span>
                    </p>
                    <p className="text-xs text-subink">
                      {it.document_code} · {it.department_name ?? '—'} · Soạn bởi {it.created_by_name ?? '—'} ·
                      Gửi {formatDateTime(it.submitted_at ?? undefined)}
                    </p>
                    {it.change_note && <p className="mt-1 text-sm text-ink">{it.change_note}</p>}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Button size="sm" variant="ghost" onClick={() => navigate(`/documents/${it.document_id}`)}>
                      <ArrowUpRight size={14} /> Xem
                    </Button>
                    <Button
                      size="sm"
                      variant="success"
                      disabled={!it.can_approve}
                      title={!it.can_approve ? 'Không thể tự duyệt phiên bản mình soạn' : undefined}
                      onClick={() => setApproveTarget(it)}
                    >
                      <Check size={14} /> Duyệt
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setRejectTarget(it)}>
                      <X size={14} /> Từ chối
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={!!approveTarget}
        onClose={() => setApproveTarget(null)}
        onConfirm={doApprove}
        title="Duyệt & ban hành"
        message={`Ban hành phiên bản v${approveTarget?.version_no} của "${approveTarget?.title}"? Phiên bản hiệu lực cũ sẽ tự động lỗi thời.`}
        confirmText="Ban hành"
        loading={approving}
      />
      {rejectTarget && (
        <RejectModal
          item={rejectTarget}
          onClose={() => setRejectTarget(null)}
          onDone={() => {
            setRejectTarget(null);
            toast.success('Đã từ chối phiên bản');
            reload();
          }}
        />
      )}
    </div>
  );
}

function RejectModal({
  item,
  onClose,
  onDone,
}: {
  item: PendingReviewItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!reason.trim()) return toast.error('Nhập lý do từ chối');
    setSubmitting(true);
    try {
      await docsApi.rejectVersion(item.document_id, item.version_id, reason.trim());
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
      title={`Từ chối phiên bản v${item.version_no}`}
      description="Phiên bản trở lại trạng thái nháp để người soạn chỉnh sửa."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button variant="danger" onClick={submit} loading={submitting}>
            Từ chối
          </Button>
        </>
      }
    >
      <Field label="Lý do từ chối" required>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
    </Modal>
  );
}
