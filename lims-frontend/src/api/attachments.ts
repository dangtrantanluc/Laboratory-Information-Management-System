/**
 * Đính kèm file (attachments) — wrapper chung cho các owner:
 * - sample  : chứng từ gửi mẫu (POST/GET /samples/{id}/attachments)
 * - result  : raw data kết quả (POST/GET /results/{result_id}/attachments)
 * - chemical: CoA / MSDS của hóa chất (POST/GET /chemicals/{id}/attachments)
 *
 * Mọi upload nhận field `file` (multipart) — dùng apiUpload sẵn có.
 * List trả về Attachment[] kèm `download_url` (presigned) — mở thẳng bằng window.open
 * giống pattern tải version tài liệu, KHÔNG cần gọi apiDownload.
 *
 * Lưu ý BE: lô (lot) chỉ có GET /lots/{id}/coa để TẢI CoA (không có endpoint upload
 * CoA theo lô qua API hiện tại) — CoA/MSDS được đính kèm ở cấp hóa chất.
 */
import { apiGet, apiUpload } from '@/lib/api';
import type { Attachment } from '@/types';

export type AttachmentOwner = 'sample' | 'result' | 'chemical';

function basePath(owner: AttachmentOwner, ownerId: string): string {
  switch (owner) {
    case 'sample':
      return `/samples/${ownerId}/attachments`;
    case 'result':
      return `/results/${ownerId}/attachments`;
    case 'chemical':
      return `/chemicals/${ownerId}/attachments`;
  }
}

export function listAttachments(owner: AttachmentOwner, ownerId: string) {
  return apiGet<Attachment[]>(basePath(owner, ownerId));
}

export function uploadAttachment(owner: AttachmentOwner, ownerId: string, file: File) {
  return apiUpload<Attachment>(basePath(owner, ownerId), file, 'file');
}

/** Mở file đính kèm bằng URL presigned trả từ list (cùng cách tải version tài liệu). */
export function openAttachment(att: Attachment) {
  if (att.download_url) window.open(att.download_url, '_blank', 'noopener');
}
