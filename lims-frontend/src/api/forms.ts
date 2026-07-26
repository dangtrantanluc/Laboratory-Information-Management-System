/**
 * Kho biểu mẫu VILAS (GĐ3).
 * - Template: QLCL quản trị (form:manage); mọi vai trò đọc/tải.
 * - Submission (minh chứng): phòng lab nộp (form:submit) → thông báo QLCL.
 * File gắn qua endpoint generic /attachments (owner_type + owner_id).
 */
import {
  apiDelete,
  apiDownload,
  apiGet,
  apiGetPaged,
  apiPatch,
  apiPost,
  apiUploadForm,
  saveBlob,
} from '@/lib/api';
import type {
  FormFileHistoryItem,
  FormFileOwner,
  FormSubmission,
  FormTemplate,
} from '@/types';

export interface TemplateFilters {
  iso_clause?: string;
  category?: string;
  q?: string;
  active_only?: boolean;
  page?: number;
  limit?: number;
}
export function listTemplates(f: TemplateFilters = {}) {
  return apiGetPaged<FormTemplate[]>('/forms/templates', { ...f });
}

/** Tải TẤT CẢ biểu mẫu (gộp mọi trang) — backend giới hạn limit 100/trang. */
export async function listAllTemplates(f: TemplateFilters = {}): Promise<FormTemplate[]> {
  const acc: FormTemplate[] = [];
  let page = 1;
  for (;;) {
    const res = await apiGetPaged<FormTemplate[]>('/forms/templates', { ...f, page, limit: 100 });
    const batch = res.data ?? [];
    acc.push(...batch);
    const total = res.meta?.total ?? acc.length;
    if (batch.length === 0 || acc.length >= total || page >= 50) break;
    page += 1;
  }
  return acc;
}
export interface TemplateBody {
  code: string;
  title: string;
  iso_clause: string;
  category?: string;
  year?: number | null;
  note?: string | null;
}
export function createTemplate(body: TemplateBody) {
  return apiPost<FormTemplate>('/forms/templates', body);
}
export function updateTemplate(id: string, body: Partial<TemplateBody> & { is_active?: boolean }) {
  return apiPatch<FormTemplate>(`/forms/templates/${id}`, body);
}

export interface SubmissionFilters {
  template_id?: string;
  department_id?: string;
  year?: number;
  status?: 'pending' | 'approved' | 'rejected';
  page?: number;
  limit?: number;
}
export function listSubmissions(f: SubmissionFilters = {}) {
  return apiGetPaged<FormSubmission[]>('/forms/submissions', { ...f });
}

/** Duyệt minh chứng (form:approve — qms/admin). */
export function approveSubmission(id: string) {
  return apiPost<FormSubmission>(`/forms/submissions/${id}/approve`, {});
}

/** Từ chối minh chứng, bắt buộc lý do (form:approve — qms/admin). */
export function rejectSubmission(id: string, reason: string) {
  return apiPost<FormSubmission>(`/forms/submissions/${id}/reject`, { reason });
}

export interface SubmissionHistoryItem {
  id: string;
  action: string;
  user_id: string | null;
  user_name: string | null;
  detail: Record<string, unknown> | null;
  at: string;
}

// ── Lịch sử TỔNG HỢP toàn kho biểu mẫu (tab "Lịch sử") ──────────
export interface FormHistoryItem {
  id: string;
  at: string;
  /** Bản tệp gắn với thao tác này — dùng để tải lại đúng bản đó (kể cả bản đã bị thay). */
  attachment_id: string | null;
  owner_type: 'form_template' | 'form_submission';
  owner_id: string;
  owner_label: string;
  form_code: string | null;
  form_title: string | null;
  department_name: string | null;
  action: string;
  action_label: string;
  file_name: string | null;
  reason: string | null;
  user_name: string | null;
}
export function listFormsHistory(
  f: { q?: string; owner_type?: string; page?: number; limit?: number } = {},
) {
  return apiGetPaged<FormHistoryItem[]>('/forms/history', { ...f });
}


/** Lịch sử duyệt (audit_logs lọc theo resource_id) — form:approve. */
export function getSubmissionHistory(id: string) {
  return apiGet<SubmissionHistoryItem[]>(`/forms/submissions/${id}/history`);
}

/** Xuất Excel danh sách minh chứng (theo cùng bộ lọc phòng/năm đang xem) — tải về máy. */
export async function exportSubmissionsXlsx(
  f: Pick<SubmissionFilters, 'template_id' | 'department_id' | 'year'> = {},
) {
  const { blob, filename } = await apiDownload('/forms/submissions/export', { ...f });
  saveBlob(blob, filename);
}
export interface SubmissionBody {
  template_id: string;
  department_id?: string | null;
  year?: number | null;
  note?: string | null;
}
export function createSubmission(body: SubmissionBody) {
  return apiPost<FormSubmission>('/forms/submissions', body);
}

/** Gắn file vào template/submission qua endpoint generic /attachments. */
export function uploadFormFile(
  ownerType: 'form_template' | 'form_submission',
  ownerId: string,
  file: File,
) {
  return apiUploadForm('/attachments', { owner_type: ownerType, owner_id: ownerId, file });
}

/** Lấy URL tải (presigned) rồi mở tab mới. */
export async function openFormFile(fileId: string) {
  const data = await apiGet<{ download_url: string }>(`/attachments/${fileId}`);
  if (data?.download_url) window.open(data.download_url, '_blank', 'noopener');
}

// ===== Tệp: tải lên / thay thế / gỡ / lịch sử =====
// Endpoint riêng theo owner (KHÔNG dùng /attachments generic) vì chỉ ở đây mới có
// RBAC form:manage / form:submit + ràng buộc phòng ban và trạng thái duyệt.
export interface ReplaceFileOptions {
  /** Lý do thay tệp — ghi vào nhật ký, hiện ở màn hình lịch sử. */
  reason?: string;
  /** Id tệp đang hiển thị; lệch với bản trên server → 409 (người khác vừa thay). */
  expectedAttachmentId?: string | null;
}

/** Tải lên tệp mới; nếu đã có tệp thì bản cũ tự chuyển thành lịch sử. */
export function replaceFormFile(
  owner: FormFileOwner,
  ownerId: string,
  file: File,
  opts: ReplaceFileOptions = {},
) {
  return apiUploadForm<FormTemplate | FormSubmission>(`/forms/${owner}/${ownerId}/file`, {
    file,
    reason: opts.reason || undefined,
    expected_attachment_id: opts.expectedAttachmentId || undefined,
  });
}

/** Gỡ tệp hiện hành của biểu mẫu gốc (minh chứng không cho gỡ — phải thay). */
export function deleteTemplateFile(templateId: string, reason?: string) {
  const qs = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  return apiDelete(`/forms/templates/${templateId}/file${qs}`);
}

/** Lịch sử tải lên: mọi bản đã dùng, ai tải, khi nào, vì sao thay. */
export function getFileHistory(owner: FormFileOwner, ownerId: string) {
  return apiGet<FormFileHistoryItem[]>(`/forms/${owner}/${ownerId}/files`);
}

/** Mở một bản trong lịch sử (kể cả bản đã bị thay — /attachments/{id} không phục vụ bản cũ). */
export async function openHistoryFile(
  owner: FormFileOwner,
  ownerId: string,
  attachmentId: string,
) {
  const data = await apiGet<{ download_url: string }>(
    `/forms/${owner}/${ownerId}/files/${attachmentId}/download`,
  );
  if (data?.download_url) window.open(data.download_url, '_blank', 'noopener');
}
