/**
 * Quản lý tệp của một biểu mẫu gốc / minh chứng: xem tệp hiện hành, tải lên hoặc
 * thay tệp, gỡ tệp, và xem lịch sử mọi bản đã dùng.
 *
 * Mô hình: mỗi biểu mẫu có ĐÚNG 1 tệp hiện hành. Thay tệp không xóa bản cũ —
 * bản cũ vào lịch sử và vẫn tải lại được (yêu cầu truy vết của VILAS/ISO 17025).
 */
import { useState } from 'react';
import { Download, FileUp, History, Trash2, Upload } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input } from '@/components/ui/Field';
import { EmptyState, Spinner } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/cn';
import type { FormFile, FormFileOwner } from '@/types';
import * as formsApi from '@/api/forms';

/** Đuôi tệp được backend chấp nhận (khớp attachment_common.GENERIC_ALLOWED_MIME). */
const ACCEPT = '.pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg';

export function formatBytes(size: number | null): string {
  if (size == null) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function FormFileManager({
  owner,
  ownerId,
  title,
  subtitle,
  currentFile,
  canEdit,
  allowDelete = false,
  onClose,
  onChanged,
}: {
  owner: FormFileOwner;
  ownerId: string;
  title: string;
  subtitle?: string;
  /** Tệp đang dùng (lấy từ files[0] của template/submission). */
  currentFile: FormFile | null;
  /** Có quyền tải lên/thay tệp không (form:manage với biểu mẫu, form:submit với minh chứng). */
  canEdit: boolean;
  /** Minh chứng bắt buộc có tệp → không cho gỡ, chỉ cho thay. */
  allowDelete?: boolean;
  onClose: () => void;
  /** Gọi sau khi tệp thay đổi để trang cha tải lại dữ liệu. */
  onChanged: () => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: history, loading: loadingHistory, reload: reloadHistory } = useAsync(
    () => formsApi.getFileHistory(owner, ownerId),
    [owner, ownerId],
  );

  async function doUpload() {
    if (!file) return toast.error('Chọn tệp trước đã');
    setBusy(true);
    try {
      await formsApi.replaceFormFile(owner, ownerId, file, {
        reason: reason.trim() || undefined,
        // Lệch với bản trên server → 409, tránh ghi đè công của người khác.
        expectedAttachmentId: currentFile?.id ?? null,
      });
      toast.success(currentFile ? 'Đã thay tệp' : 'Đã tải tệp lên');
      setFile(null);
      setReason('');
      setConfirmReplace(false);
      reloadHistory();
      onChanged();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  async function doDelete() {
    setBusy(true);
    try {
      await formsApi.deleteTemplateFile(ownerId, reason.trim() || undefined);
      toast.success('Đã gỡ tệp — vẫn xem lại được trong lịch sử');
      setReason('');
      setConfirmDelete(false);
      reloadHistory();
      onChanged();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  function openFile(attachmentId: string) {
    formsApi
      .openHistoryFile(owner, ownerId, attachmentId)
      .catch((e) => toast.error(describeError(e).title));
  }

  const items = history ?? [];

  return (
    <>
      <Modal open onClose={onClose} title={title} description={subtitle} size="lg">
        <div className="flex flex-col gap-5">
          {/* ── Tệp hiện hành ── */}
          <section>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-subink">
              Tệp hiện hành
            </h3>
            {currentFile ? (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-hairline bg-surface2 p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink" title={currentFile.file_name}>
                    {currentFile.file_name}
                  </p>
                  <p className="text-xs text-subink">
                    {formatBytes(currentFile.size)} · tải lên {formatDateTime(currentFile.uploaded_at)}
                  </p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => openFile(currentFile.id)}>
                  <Download size={14} /> Tải về
                </Button>
                {canEdit && allowDelete && (
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
                    <Trash2 size={14} /> Gỡ tệp
                  </Button>
                )}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-hairline p-3 text-sm text-subink">
                Chưa có tệp nào.
              </p>
            )}
          </section>

          {/* ── Tải lên / thay tệp ── */}
          {canEdit && (
            <section>
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-subink">
                {currentFile ? 'Thay tệp' : 'Tải tệp lên'}
              </h3>
              <div className="flex flex-col gap-3 rounded-lg border border-hairline p-3">
                <label
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-3 py-4 transition-colors',
                    file
                      ? 'border-blueberry/50 bg-blueberry/5'
                      : 'border-hairline hover:border-blueberry/40 hover:bg-blueberry/5',
                  )}
                >
                  <FileUp size={20} className="shrink-0 text-blueberry" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {file ? file.name : 'Chọn tệp…'}
                    </p>
                    <p className="text-xs text-subink">
                      {file ? formatBytes(file.size) : 'PDF, Word, Excel, CSV hoặc ảnh'}
                    </p>
                  </div>
                  <input
                    type="file"
                    accept={ACCEPT}
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </label>
                <Field label="Lý do thay đổi (tùy chọn)">
                  <Input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="vd cập nhật theo phiên bản 2026"
                  />
                </Field>
                <div className="flex justify-end">
                  <Button
                    onClick={() => (currentFile ? setConfirmReplace(true) : doUpload())}
                    loading={busy}
                    disabled={!file}
                  >
                    <Upload size={16} /> {currentFile ? 'Thay tệp' : 'Tải lên'}
                  </Button>
                </div>
              </div>
            </section>
          )}

          {/* ── Lịch sử tải lên ── */}
          <section>
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-subink">
              <History size={13} /> Lịch sử tải lên
              {items.length > 0 && <span className="font-semibold">({items.length})</span>}
            </h3>
            {loadingHistory ? (
              <div className="flex justify-center py-6">
                <Spinner className="h-5 w-5" />
              </div>
            ) : items.length === 0 ? (
              <EmptyState title="Chưa có lượt tải lên nào" />
            ) : (
              <ul className="flex flex-col gap-2">
                {items.map((h) => (
                  <li
                    key={h.id}
                    className={cn(
                      'rounded-lg border p-3 transition-colors',
                      h.is_current ? 'border-blueberry/40 bg-blueberry/5' : 'border-hairline',
                    )}
                  >
                    <div className="flex flex-wrap items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-sm font-medium text-ink" title={h.file_name}>
                            {h.file_name}
                          </span>
                          {h.is_current ? (
                            <Badge tone="success">Hiện hành</Badge>
                          ) : (
                            <Badge tone="muted">Đã thay</Badge>
                          )}
                          {h.action_label && <Badge tone="neutral">{h.action_label}</Badge>}
                        </div>
                        <p className="mt-0.5 text-xs text-subink">
                          {formatBytes(h.size)} · {h.uploaded_by_name ?? 'Không rõ'} ·{' '}
                          {formatDateTime(h.uploaded_at)}
                          {h.replaced_at && ` · thay lúc ${formatDateTime(h.replaced_at)}`}
                        </p>
                        {(h.reason || h.removed_reason) && (
                          <p className="mt-1 text-xs italic text-subink">
                            {h.reason && `Lý do tải lên: ${h.reason}`}
                            {h.reason && h.removed_reason && ' · '}
                            {h.removed_reason && `Lý do bị thay: ${h.removed_reason}`}
                          </p>
                        )}
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => openFile(h.id)}>
                        <Download size={14} /> Tải
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmReplace}
        onClose={() => setConfirmReplace(false)}
        onConfirm={doUpload}
        loading={busy}
        tone="primary"
        confirmText="Thay tệp"
        title="Thay tệp hiện hành?"
        message={`Tệp "${currentFile?.file_name ?? ''}" sẽ chuyển thành bản lưu trữ (vẫn xem lại được trong lịch sử). Người dùng sẽ tải về bản mới.`}
      />
      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={doDelete}
        loading={busy}
        confirmText="Gỡ tệp"
        title="Gỡ tệp khỏi biểu mẫu?"
        message="Biểu mẫu sẽ không còn tệp để tải về. Bản tệp vẫn được lưu trong lịch sử."
      />
    </>
  );
}
