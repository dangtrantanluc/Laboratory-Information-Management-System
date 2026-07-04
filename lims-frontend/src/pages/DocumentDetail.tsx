import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FileText,
  Download,
  Send,
  Check,
  X,
  Plus,
  History as HistoryIcon,
  BarChart3,
  Pencil,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Textarea } from '@/components/ui/Field';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DocVersionStatusBadge, SecurityLevelBadge } from '@/components/ui/StatusBadge';
import { FileDrop } from '@/pages/Documents';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canApproveDocuments, canManageDocuments, canViewDocumentStats } from '@/lib/rbac';
import type { DocumentVersion } from '@/types';
import * as docsApi from '@/api/documents';

const MAX_FILE_MB = 20;

function formatSize(bytes?: number): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const { data, loading, reload } = useAsync(() => docsApi.getDocument(id), [id]);

  const [newVersionOpen, setNewVersionOpen] = useState(false);
  const [editMetaOpen, setEditMetaOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [statsOpen, setStatsOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<DocumentVersion | null>(null);
  const [approveTarget, setApproveTarget] = useState<DocumentVersion | null>(null);
  const [busyVersionId, setBusyVersionId] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);

  if (loading) return <LoadingState />;
  if (!data)
    return (
      <Card>
        <EmptyState title="Không tìm thấy tài liệu" description="Tài liệu không tồn tại hoặc bạn không có quyền truy cập." />
      </Card>
    );

  const canManage = canManageDocuments(user);
  const canApprove = canApproveDocuments(user);
  const isAuthor = (v: DocumentVersion) => !!v.created_by_name && v.created_by_name === user?.full_name;

  async function download(versionId: string) {
    try {
      const info = await docsApi.getDownloadInfo(id, versionId);
      if (info.obsolete_warning) toast.error(info.obsolete_warning);
      // mở presigned URL trong tab mới để tải.
      window.open(info.download_url, '_blank', 'noopener');
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  async function submitReview(versionId: string) {
    setBusyVersionId(versionId);
    try {
      await docsApi.submitReview(id, versionId);
      toast.success('Đã gửi duyệt phiên bản');
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusyVersionId(null);
    }
  }

  async function doApprove() {
    if (!approveTarget) return;
    setApproving(true);
    try {
      await docsApi.approveVersion(id, approveTarget.id);
      toast.success('Đã ban hành phiên bản');
      setApproveTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setApproving(false);
    }
  }

  // Tối đa 1 phiên bản nháp/chờ duyệt tại 1 thời điểm → ẩn nút "Phiên bản mới" khi đang có.
  const hasOpenVersion = data.versions.some((v) => v.status === 'draft' || v.status === 'review');

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/documents')}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Danh sách tài liệu
      </button>

      <PageHeader
        title={data.title}
        description={`${data.document_code} · ${data.department_name ?? '—'}`}
        icon={<FileText size={20} />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => setHistoryOpen(true)}>
              <HistoryIcon size={16} /> Lịch sử
            </Button>
            {canViewDocumentStats(user) && (
              <Button variant="secondary" onClick={() => setStatsOpen(true)}>
                <BarChart3 size={16} /> Truy cập
              </Button>
            )}
            {canManage && (
              <Button variant="secondary" onClick={() => setEditMetaOpen(true)}>
                <Pencil size={16} /> Sửa thông tin
              </Button>
            )}
            {canManage && !hasOpenVersion && (
              <Button onClick={() => setNewVersionOpen(true)}>
                <Plus size={16} /> Phiên bản mới
              </Button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Thông tin tài liệu */}
        <Card>
          <CardHeader title="Thông tin tài liệu" />
          <CardBody className="flex flex-col gap-2.5 text-sm">
            <Row label="Mã tài liệu" value={data.document_code} />
            <Row label="Loại" value={data.type_label} />
            <Row label="Phòng ban" value={data.department_name ?? '—'} />
            <div className="flex justify-between gap-4">
              <span className="shrink-0 text-subink">Mức bảo mật</span>
              <SecurityLevelBadge level={data.security_level} />
            </div>
            <Row label="Người tạo" value={data.created_by_name ?? '—'} />
            <Row label="Ngày tạo" value={formatDate(data.created_at)} />
          </CardBody>
        </Card>

        {/* Phiên bản hiệu lực */}
        <Card className="lg:col-span-2">
          <CardHeader title="Phiên bản hiệu lực" />
          <CardBody>
            {data.current_version ? (
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-lg font-bold text-ink">v{data.current_version.version_no}</span>
                  <DocVersionStatusBadge status={data.current_version.status} />
                  <span className="text-xs text-subink">
                    Ban hành {formatDateTime(data.current_version.approved_at ?? undefined)} ·{' '}
                    {data.current_version.approved_by_name ?? '—'}
                  </span>
                </div>
                {data.current_version.change_note && (
                  <p className="text-sm text-ink">{data.current_version.change_note}</p>
                )}
                <div className="flex items-center justify-between gap-3 rounded-lg border border-hairline bg-plate/40 px-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">
                      {data.current_version.file?.filename ?? '—'}
                    </p>
                    <p className="text-xs text-subink">{formatSize(data.current_version.file?.size)}</p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => download(data.current_version!.id)}>
                    <Download size={14} /> Tải về
                  </Button>
                </div>
              </div>
            ) : (
              <EmptyState
                title="Chưa có phiên bản ban hành"
                description="Tài liệu chưa có phiên bản nào được duyệt và ban hành."
              />
            )}
          </CardBody>
        </Card>
      </div>

      {/* Danh sách / lịch sử phiên bản */}
      <Card>
        <CardHeader title={`Các phiên bản (${data.versions.length})`} subtitle="Quy trình: Nháp → Chờ duyệt → Hiệu lực → Lỗi thời" />
        <CardBody className="p-0">
          {data.versions.length === 0 ? (
            <EmptyState title="Chưa có phiên bản" />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {[...data.versions]
                .sort((a, b) => b.version_no - a.version_no)
                .map((v) => {
                  const authored = isAuthor(v);
                  const canApproveThis = canApprove && !authored;
                  return (
                    <li key={v.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-ink">v{v.version_no}</span>
                          <DocVersionStatusBadge status={v.status} />
                          {v.is_obsolete && v.obsolete_label && (
                            <Badge tone="overdue">{v.obsolete_label}</Badge>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-subink">
                          {v.created_by_name ?? '—'} · {formatDateTime(v.created_at)}
                          {v.change_note ? ` · ${v.change_note}` : ''}
                        </p>
                        {v.status === 'draft' && v.reject_reason && (
                          <p className="mt-1 text-xs text-overdue">Bị từ chối: {v.reject_reason}</p>
                        )}
                      </div>

                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        {v.file && (
                          <Button size="sm" variant="ghost" onClick={() => download(v.id)}>
                            <Download size={14} /> Tải
                          </Button>
                        )}
                        {/* draft: gửi duyệt (người soạn/leader/admin) */}
                        {v.status === 'draft' && canManage && (
                          <Button
                            size="sm"
                            onClick={() => submitReview(v.id)}
                            loading={busyVersionId === v.id}
                          >
                            <Send size={14} /> Gửi duyệt
                          </Button>
                        )}
                        {/* review: duyệt + từ chối (trưởng nhóm/leader/admin, không phải người soạn) */}
                        {v.status === 'review' && canApprove && (
                          <>
                            <Button
                              size="sm"
                              variant="success"
                              disabled={!canApproveThis}
                              title={!canApproveThis ? 'Không thể tự duyệt phiên bản mình soạn' : undefined}
                              onClick={() => setApproveTarget(v)}
                            >
                              <Check size={14} /> Duyệt
                            </Button>
                            <Button size="sm" variant="danger" onClick={() => setRejectTarget(v)}>
                              <X size={14} /> Từ chối
                            </Button>
                          </>
                        )}
                      </div>
                    </li>
                  );
                })}
            </ul>
          )}
        </CardBody>
      </Card>

      {newVersionOpen && (
        <NewVersionModal
          documentId={id}
          hasPriorVersion={data.versions.length > 0}
          onClose={() => setNewVersionOpen(false)}
          onCreated={() => {
            setNewVersionOpen(false);
            toast.success('Đã tạo phiên bản mới (nháp)');
            reload();
          }}
        />
      )}
      {editMetaOpen && (
        <EditMetaModal
          documentId={id}
          initial={{ title: data.title, type: data.type, security_level: data.security_level }}
          onClose={() => setEditMetaOpen(false)}
          onSaved={() => {
            setEditMetaOpen(false);
            toast.success('Đã cập nhật thông tin tài liệu');
            reload();
          }}
        />
      )}
      {rejectTarget && (
        <RejectModal
          documentId={id}
          version={rejectTarget}
          onClose={() => setRejectTarget(null)}
          onDone={() => {
            setRejectTarget(null);
            toast.success('Đã từ chối phiên bản');
            reload();
          }}
        />
      )}
      <ConfirmDialog
        open={!!approveTarget}
        onClose={() => setApproveTarget(null)}
        onConfirm={doApprove}
        title="Duyệt & ban hành phiên bản"
        message={`Ban hành phiên bản v${approveTarget?.version_no}? Phiên bản hiệu lực cũ (nếu có) sẽ tự động chuyển sang lỗi thời.`}
        confirmText="Ban hành"
        loading={approving}
      />
      {historyOpen && <HistoryModal documentId={id} onClose={() => setHistoryOpen(false)} />}
      {statsOpen && <DocStatsModal documentId={id} onClose={() => setStatsOpen(false)} />}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="shrink-0 text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function NewVersionModal({
  documentId,
  hasPriorVersion,
  onClose,
  onCreated,
}: {
  documentId: string;
  hasPriorVersion: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [changeNote, setChangeNote] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!file) return toast.error('Chọn tệp nội dung phiên bản');
    if (hasPriorVersion && !changeNote.trim())
      return toast.error('Bắt buộc ghi chú thay đổi từ phiên bản thứ 2');
    if (file.size > MAX_FILE_MB * 1024 * 1024) return toast.error(`Tệp vượt quá ${MAX_FILE_MB}MB`);
    setSubmitting(true);
    try {
      await docsApi.createVersion(documentId, { change_note: changeNote.trim() || undefined, file });
      onCreated();
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
      title="Tạo phiên bản mới"
      description="Phiên bản mới ở trạng thái nháp; phiên bản hiệu lực hiện tại không thay đổi cho đến khi bản mới được ban hành."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo phiên bản
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Ghi chú thay đổi" required={hasPriorVersion}>
          <Textarea
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            placeholder="vd: Bổ sung mục an toàn hóa chất"
          />
        </Field>
        <Field label="Tệp nội dung" required hint="PDF, DOCX, XLSX, PNG, JPG · tối đa 20MB">
          <FileDrop file={file} onSelect={setFile} />
        </Field>
      </div>
    </Modal>
  );
}

function EditMetaModal({
  documentId,
  initial,
  onClose,
  onSaved,
}: {
  documentId: string;
  initial: { title: string; type: string; security_level: 'internal' | 'restricted' };
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [title, setTitle] = useState(initial.title);
  const [security, setSecurity] = useState(initial.security_level);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề');
    setSubmitting(true);
    try {
      await docsApi.updateDocument(documentId, { title: title.trim(), security_level: security });
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
      title="Sửa thông tin tài liệu"
      description="Mã tài liệu không thể thay đổi sau khi tạo."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Tiêu đề" required>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Mức bảo mật" required>
          <select
            value={security}
            onChange={(e) => setSecurity(e.target.value as 'internal' | 'restricted')}
            className="h-10 w-full rounded-lg border border-hairline bg-white px-3 text-sm text-ink"
          >
            <option value="internal">Nội bộ</option>
            <option value="restricted">Hạn chế</option>
          </select>
        </Field>
      </div>
    </Modal>
  );
}

function RejectModal({
  documentId,
  version,
  onClose,
  onDone,
}: {
  documentId: string;
  version: DocumentVersion;
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
      await docsApi.rejectVersion(documentId, version.id, reason.trim());
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
      title={`Từ chối phiên bản v${version.version_no}`}
      description="Phiên bản sẽ trở lại trạng thái nháp để người soạn chỉnh sửa và gửi lại."
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
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="vd: Thiếu mục an toàn hóa chất" />
      </Field>
    </Modal>
  );
}

function HistoryModal({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const { data, loading } = useAsync(() => docsApi.getHistory(documentId), [documentId]);

  return (
    <Modal open onClose={onClose} size="lg" title="Lịch sử thay đổi">
      {loading ? (
        <LoadingState />
      ) : !data || data.timeline.length === 0 ? (
        <EmptyState title="Chưa có lịch sử" />
      ) : (
        <div className="flex flex-col gap-5">
          {data.timeline
            .slice()
            .sort((a, b) => b.version_no - a.version_no)
            .map((g) => (
              <div key={g.version_no}>
                <p className="mb-2 text-sm font-semibold text-ink">Phiên bản v{g.version_no}</p>
                <ul className="flex flex-col gap-2 border-l-2 border-hairline pl-4">
                  {g.events.map((ev, i) => (
                    <li key={i} className="text-sm">
                      <span className="font-medium text-ink">{actionLabel(ev.action)}</span>
                      <span className="text-subink">
                        {' '}
                        · {ev.by_name ?? '—'} · {formatDateTime(ev.at)}
                      </span>
                      {ev.detail && <p className="text-xs text-subink">{ev.detail}</p>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
        </div>
      )}
    </Modal>
  );
}

const ACTION_LABELS: Record<string, string> = {
  DOCUMENT_VERSION_CREATE: 'Tạo phiên bản',
  DOCUMENT_VERSION_SUBMIT: 'Gửi duyệt',
  DOCUMENT_VERSION_APPROVE: 'Duyệt & ban hành',
  DOCUMENT_VERSION_REJECT: 'Từ chối',
  DOCUMENT_VERSION_OBSOLETE: 'Chuyển lỗi thời',
  DOCUMENT_VERSION_UPDATE: 'Cập nhật phiên bản',
  DOCUMENT_CREATE: 'Tạo tài liệu',
  DOCUMENT_UPDATE: 'Cập nhật tài liệu',
};
function actionLabel(a: string): string {
  return ACTION_LABELS[a] ?? a;
}

function DocStatsModal({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const { data, loading } = useAsync(
    () => docsApi.getDocumentAccessStats(documentId, { group_by: 'day' }),
    [documentId],
  );

  return (
    <Modal open onClose={onClose} title="Thống kê truy cập tài liệu">
      {loading ? (
        <LoadingState />
      ) : !data ? (
        <EmptyState title="Chưa có dữ liệu" />
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-subink">
            Khoảng: {data.range.from} → {data.range.to}
          </p>
          <div className="grid grid-cols-3 gap-3">
            <StatBox label="Lượt xem" value={data.totals.view} tone="info" />
            <StatBox label="Lượt tải" value={data.totals.download} tone="success" />
            <StatBox label="Lượt sửa" value={data.totals.edit} tone="warning" />
          </div>
          {data.series && data.series.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs uppercase text-stem">
                    <th className="py-2">Ngày</th>
                    <th className="py-2 text-right">Xem</th>
                    <th className="py-2 text-right">Tải</th>
                    <th className="py-2 text-right">Sửa</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {data.series.map((s) => (
                    <tr key={s.period}>
                      <td className="py-2">{formatDate(s.period)}</td>
                      <td className="py-2 text-right">{s.view}</td>
                      <td className="py-2 text-right">{s.download}</td>
                      <td className="py-2 text-right">{s.edit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function StatBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'info' | 'success' | 'warning';
}) {
  const toneCls = {
    info: 'text-berry',
    success: 'text-success',
    warning: 'text-[#b45309]',
  }[tone];
  return (
    <div className="rounded-lg border border-hairline bg-plate/40 px-4 py-3 text-center">
      <p className={`text-2xl font-bold ${toneCls}`}>{value}</p>
      <p className="mt-0.5 text-xs text-subink">{label}</p>
    </div>
  );
}
