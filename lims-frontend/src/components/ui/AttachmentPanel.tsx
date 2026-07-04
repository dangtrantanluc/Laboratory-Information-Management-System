/**
 * Khối đính kèm dùng chung: chọn file → upload → liệt kê → tải về.
 * - Dùng cho hóa chất (CoA/MSDS), mẫu (chứng từ gửi mẫu), kết quả (raw data).
 * - Tái dùng FileDrop (Documents) + apiUpload (lib/api). Tải về mở download_url presigned.
 * - Toast tiếng Việt theo error.code qua describeError.
 */
import { useState } from 'react';
import { Download, Paperclip, UploadCloud } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { FileDrop } from '@/pages/Documents';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import * as attachmentsApi from '@/api/attachments';
import type { AttachmentOwner } from '@/api/attachments';

/** Định dạng BE chấp nhận cho attachment: PDF/PNG/JPG/XLSX. */
const ACCEPT = '.pdf,.png,.jpg,.jpeg,.xlsx';

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function AttachmentPanel({
  owner,
  ownerId,
  canUpload = true,
  uploadHint = 'PDF, PNG, JPG, XLSX',
}: {
  owner: AttachmentOwner;
  ownerId: string;
  canUpload?: boolean;
  uploadHint?: string;
}) {
  const toast = useToast();
  const listQ = useAsync(() => attachmentsApi.listAttachments(owner, ownerId), [owner, ownerId]);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  async function doUpload() {
    if (!file) return toast.error('Chọn tệp để tải lên');
    setUploading(true);
    try {
      await attachmentsApi.uploadAttachment(owner, ownerId, file);
      setFile(null);
      listQ.reload();
      toast.success('Đã tải tệp lên');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setUploading(false);
    }
  }

  const items = listQ.data ?? [];

  return (
    <div className="flex flex-col gap-3">
      {canUpload && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex-1">
            <FileDrop file={file} onSelect={setFile} accept={ACCEPT} />
          </div>
          <Button onClick={doUpload} loading={uploading} disabled={!file}>
            <UploadCloud size={16} /> Tải lên
          </Button>
        </div>
      )}
      {canUpload && <p className="-mt-1 text-xs text-subink">{uploadHint}</p>}

      {listQ.loading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState icon={<Paperclip size={18} />} title="Chưa có tệp đính kèm" />
      ) : (
        <ul className="flex flex-col divide-y divide-hairline rounded-lg border border-hairline">
          {items.map((att) => (
            <li key={att.id} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <Paperclip size={15} className="shrink-0 text-stem" />
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{att.file_name}</p>
                  <p className="text-xs text-subink">
                    {humanSize(att.size)} · {formatDateTime(att.uploaded_at)}
                    {att.uploaded_by_name ? ` · ${att.uploaded_by_name}` : ''}
                  </p>
                </div>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => attachmentsApi.openAttachment(att)}
                disabled={!att.download_url}
                title="Tải về"
              >
                <Download size={14} /> Tải
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
