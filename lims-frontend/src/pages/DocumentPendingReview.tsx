import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardCheck, Check, X, ArrowUpRight, History, Download } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Textarea } from '@/components/ui/Field';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { PendingReviewItem, FormSubmission } from '@/types';
import * as docsApi from '@/api/documents';
import * as formsApi from '@/api/forms';
import type { SubmissionHistoryItem } from '@/api/forms';

export function DocumentPendingReview() {
  const toast = useToast();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data, loading, reload } = useAsync(() => docsApi.listPendingReview({ limit: 100 }), []);
  const showEvidenceApproval = user?.role === 'qms' || user?.role === 'admin';

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

      {showEvidenceApproval && <EvidenceApprovalSection />}

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

/** Khối duyệt minh chứng VILAS — chỉ hiện với qms/admin (form:approve), tách biệt khỏi duyệt tài liệu ISO ở trên. */
function EvidenceApprovalSection() {
  const toast = useToast();
  const { data, loading, reload } = useAsync(
    () => formsApi.listSubmissions({ status: 'pending', limit: 100 }),
    [],
  );
  const [approveTarget, setApproveTarget] = useState<FormSubmission | null>(null);
  const [rejectTarget, setRejectTarget] = useState<FormSubmission | null>(null);
  const [historyTarget, setHistoryTarget] = useState<FormSubmission | null>(null);
  const [approving, setApproving] = useState(false);

  const items = data?.data ?? [];

  async function doApprove() {
    if (!approveTarget) return;
    setApproving(true);
    try {
      await formsApi.approveSubmission(approveTarget.id);
      toast.success('Đã duyệt minh chứng');
      setApproveTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setApproving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Minh chứng VILAS chờ duyệt"
        subtitle="Minh chứng biểu mẫu do các phòng nộp lên, đang chờ Phòng QLCL duyệt"
      />
      <CardBody className="p-0">
        {loading ? (
          <LoadingState />
        ) : items.length === 0 ? (
          <EmptyState title="Không có minh chứng chờ duyệt" description="Mọi minh chứng đã được xử lý." />
        ) : (
          <ul className="flex flex-col divide-y divide-hairline">
            {items.map((s) => (
              <li
                key={s.id}
                className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="font-semibold text-ink">
                    {s.template_code} <span className="text-subink">— {s.template_title}</span>
                  </p>
                  <p className="text-xs text-subink">
                    {s.department_name ?? '—'} · Nộp bởi {s.submitted_by_name ?? '—'} ·{' '}
                    {formatDateTime(s.submitted_at)}
                    {s.year ? ` · Năm ${s.year}` : ''}
                  </p>
                  {s.files.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-3">
                      {s.files.map((f) => (
                        <button
                          key={f.id}
                          className="inline-flex items-center gap-1 text-sm text-blueberry hover:underline"
                          onClick={() =>
                            formsApi.openFormFile(f.id).catch((e) => toast.error(describeError(e).title))
                          }
                        >
                          <Download size={14} /> {f.file_name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setHistoryTarget(s)}>
                    <History size={14} /> Lịch sử
                  </Button>
                  <Button size="sm" variant="success" onClick={() => setApproveTarget(s)}>
                    <Check size={14} /> Duyệt
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => setRejectTarget(s)}>
                    <X size={14} /> Từ chối
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>

      <ConfirmDialog
        open={!!approveTarget}
        onClose={() => setApproveTarget(null)}
        onConfirm={doApprove}
        title="Duyệt minh chứng"
        message={`Duyệt minh chứng "${approveTarget?.template_code}" của phòng ${approveTarget?.department_name ?? ''}?`}
        confirmText="Duyệt"
        loading={approving}
      />
      {rejectTarget && (
        <EvidenceRejectModal
          item={rejectTarget}
          onClose={() => setRejectTarget(null)}
          onDone={() => {
            setRejectTarget(null);
            toast.success('Đã từ chối minh chứng');
            reload();
          }}
        />
      )}
      {historyTarget && (
        <EvidenceHistoryModal item={historyTarget} onClose={() => setHistoryTarget(null)} />
      )}
    </Card>
  );
}

function EvidenceRejectModal({
  item,
  onClose,
  onDone,
}: {
  item: FormSubmission;
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
      await formsApi.rejectSubmission(item.id, reason.trim());
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
      title={`Từ chối minh chứng ${item.template_code ?? ''}`}
      description="Người nộp sẽ nhận được thông báo kèm lý do từ chối."
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

function EvidenceHistoryModal({ item, onClose }: { item: FormSubmission; onClose: () => void }) {
  const { data, loading } = useAsync(() => formsApi.getSubmissionHistory(item.id), [item.id]);
  const history: SubmissionHistoryItem[] = data ?? [];

  return (
    <Modal
      open
      onClose={onClose}
      title={`Lịch sử duyệt — ${item.template_code ?? ''}`}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Đóng
        </Button>
      }
    >
      {loading ? (
        <LoadingState />
      ) : history.length === 0 ? (
        <EmptyState title="Chưa có lịch sử" description="Minh chứng này chưa có hành động duyệt nào." />
      ) : (
        <ul className="flex flex-col gap-3">
          {history.map((h) => (
            <li key={h.id} className="border-b border-hairline pb-2 last:border-0 last:pb-0">
              <p className="text-sm font-medium text-ink">{_historyLabel(h.action)}</p>
              <p className="text-xs text-subink">
                {h.user_name ?? 'Hệ thống'} · {formatDateTime(h.at)}
              </p>
              {h.detail && Object.keys(h.detail).length > 0 && (
                <p className="mt-0.5 text-xs text-subink">
                  {Object.entries(h.detail)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(' · ')}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

function _historyLabel(action: string): string {
  const labels: Record<string, string> = {
    FORM_SUBMISSION_CREATE: 'Đã nộp minh chứng',
    FORM_SUBMISSION_APPROVE: 'Đã duyệt',
    FORM_SUBMISSION_REJECT: 'Đã từ chối',
  };
  return labels[action] ?? action;
}
