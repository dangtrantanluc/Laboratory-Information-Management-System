import {
  apiDownload,
  apiGet,
  apiGetPaged,
  apiPatch,
  apiPost,
  apiUploadForm,
  saveBlob,
} from '@/lib/api';
import type {
  AccessStatsAggregate,
  ApproveVersionResult,
  ConfidentialityLevel,
  CreatedDocument,
  DocumentAccessStats,
  DocumentDetail,
  DocumentHistory,
  DocumentListItem,
  DocumentType,
  DocumentTypeMeta,
  DocumentVersion,
  DownloadInfo,
  PendingReviewItem,
  SecurityLevel,
} from '@/types';

// ── Danh mục ────────────────────────────────────────────────────
export function listDocumentTypes() {
  return apiGet<DocumentTypeMeta[]>('/document-types');
}
export function listConfidentialityLevels() {
  return apiGet<ConfidentialityLevel[]>('/confidentiality-levels');
}

// ── Tài liệu ────────────────────────────────────────────────────
export interface DocumentFilters {
  q?: string;
  type?: string;
  department_id?: string;
  security_level?: string;
  status?: string;
  page?: number;
  limit?: number;
}
export function listDocuments(f: DocumentFilters = {}) {
  return apiGetPaged<DocumentListItem[]>('/documents', { ...f });
}
export function getDocument(id: string) {
  return apiGet<DocumentDetail>(`/documents/${id}`);
}

export interface CreateDocumentInput {
  title: string;
  type: DocumentType;
  department_id?: string | null;
  security_level?: SecurityLevel;
  change_note?: string | null;
  file: File;
}
export function createDocument(input: CreateDocumentInput) {
  return apiUploadForm<CreatedDocument>('/documents', {
    title: input.title,
    type: input.type,
    department_id: input.department_id ?? undefined,
    security_level: input.security_level ?? undefined,
    change_note: input.change_note ?? undefined,
    file: input.file,
  });
}

export interface UpdateDocumentBody {
  title?: string;
  type?: string;
  security_level?: SecurityLevel;
}
export function updateDocument(id: string, body: UpdateDocumentBody) {
  return apiPatch<DocumentDetail>(`/documents/${id}`, body);
}

// ── Version ─────────────────────────────────────────────────────
export interface CreateVersionInput {
  change_note?: string | null;
  file: File;
}
export function createVersion(documentId: string, input: CreateVersionInput) {
  return apiUploadForm<DocumentVersion>(`/documents/${documentId}/versions`, {
    change_note: input.change_note ?? undefined,
    file: input.file,
  });
}

export function getVersion(documentId: string, versionId: string) {
  return apiGet<DocumentVersion>(`/documents/${documentId}/versions/${versionId}`);
}

/** Sửa change_note của version draft (JSON). */
export function updateVersionNote(documentId: string, versionId: string, change_note: string) {
  return apiPatch<DocumentVersion>(`/documents/${documentId}/versions/${versionId}`, { change_note });
}

/** Thay file version draft (multipart PUT). */
export function replaceVersionFile(
  documentId: string,
  versionId: string,
  input: { file: File; change_note?: string | null },
) {
  return apiUploadForm<DocumentVersion>(
    `/documents/${documentId}/versions/${versionId}/file`,
    { file: input.file, change_note: input.change_note ?? undefined },
    { method: 'PUT' },
  );
}

// ── State machine ───────────────────────────────────────────────
export function submitReview(documentId: string, versionId: string) {
  return apiPost<DocumentVersion>(`/documents/${documentId}/versions/${versionId}/submit-review`);
}
export function approveVersion(documentId: string, versionId: string, note?: string) {
  return apiPost<ApproveVersionResult>(
    `/documents/${documentId}/versions/${versionId}/approve`,
    note ? { note } : undefined,
  );
}
export function rejectVersion(documentId: string, versionId: string, reject_reason: string) {
  return apiPost<DocumentVersion>(`/documents/${documentId}/versions/${versionId}/reject`, {
    reject_reason,
  });
}

// ── Tải file ────────────────────────────────────────────────────
/** Lấy presigned URL + metadata để tải file version. Backend tự ghi access_log. */
export function getDownloadInfo(documentId: string, versionId: string) {
  return apiGet<DownloadInfo>(`/documents/${documentId}/versions/${versionId}/download`);
}

// ── Lịch sử ─────────────────────────────────────────────────────
export function getHistory(documentId: string) {
  return apiGet<DocumentHistory>(`/documents/${documentId}/history`);
}

// ── Hàng đợi chờ duyệt ──────────────────────────────────────────
export interface PendingReviewFilters {
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listPendingReview(f: PendingReviewFilters = {}) {
  return apiGetPaged<PendingReviewItem[]>('/documents/pending-review', { ...f });
}

// ── Thống kê truy cập (R15) ─────────────────────────────────────
export interface DocAccessStatsFilters {
  from?: string;
  to?: string;
  group_by?: 'day' | 'week' | 'month';
}
export function getDocumentAccessStats(documentId: string, f: DocAccessStatsFilters = {}) {
  return apiGet<DocumentAccessStats>(`/documents/${documentId}/access-stats`, { ...f });
}

export interface AggregateStatsFilters {
  from?: string;
  to?: string;
  department_id?: string;
  action?: 'view' | 'download' | 'edit';
  top?: number;
  sort_by?: 'view' | 'download' | 'edit' | 'total';
}
export function getAccessStatsAggregate(f: AggregateStatsFilters = {}) {
  return apiGet<AccessStatsAggregate>('/documents/access-stats', { ...f });
}

export async function exportAccessStats(f: AggregateStatsFilters = {}) {
  const { blob, filename } = await apiDownload('/documents/access-stats/export', { ...f });
  saveBlob(blob, filename);
}
