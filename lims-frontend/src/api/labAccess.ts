import { apiDelete, apiDownload, apiGetPaged, apiPatch, apiPost, apiUploadForm, saveBlob } from '@/lib/api';
import type { LabAccessCard } from '@/types';

export interface LabAccessCardFilters {
  q?: string;
  supervisor_name?: string;
  room?: string;
  active_on?: string;
  page?: number;
  limit?: number;
}
export function listLabAccessCards(f: LabAccessCardFilters = {}) {
  return apiGetPaged<LabAccessCard[]>('/lab-access-cards', { ...f });
}

export interface LabAccessCardBody {
  student_name?: string;
  class_name?: string | null;
  student_code?: string;
  email?: string | null;
  room?: string | null;
  purpose?: string | null;
  supervisor_name?: string | null;
  valid_from?: string;
  valid_to?: string | null;
  note?: string | null;
}
export function createLabAccessCard(body: LabAccessCardBody) {
  return apiPost<LabAccessCard>('/lab-access-cards', body);
}
export function updateLabAccessCard(id: string, body: LabAccessCardBody) {
  return apiPatch<LabAccessCard>(`/lab-access-cards/${id}`, body);
}
export function deleteLabAccessCard(id: string) {
  return apiDelete(`/lab-access-cards/${id}`);
}

export interface LabAccessImportResult {
  dry_run: boolean;
  sheet: string;
  total_rows: number;
  created: number;
  updated: number;
  unchanged: number;
  errors: { row: number; student_code: string | null; message: string }[];
  items: { row: number; student_code: string; student_name: string; action: 'create' | 'update' | 'unchanged' }[];
}

/**
 * Nhập file Excel "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN" — đối chiếu theo MSSV.
 * dryRun = true: chỉ xem trước sẽ tạo/sửa gì, không ghi.
 */
export function importLabAccessCards(file: File, dryRun: boolean) {
  return apiUploadForm<LabAccessImportResult>(
    `/lab-access-cards/import?dry_run=${dryRun}`,
    { file },
  );
}

/** Xuất Excel đúng bố cục file gốc; quý/năm chỉ ghi lên tiêu đề và tên sheet. */
export async function exportLabAccessCards(params: {
  q?: string;
  supervisor_name?: string;
  quarter?: number;
  year?: number;
}) {
  const { blob, filename } = await apiDownload('/lab-access-cards/export.xlsx', { ...params });
  saveBlob(blob, filename);
}
