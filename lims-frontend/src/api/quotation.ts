/**
 * m29 — BÁO GIÁ. Số tiền là STRING (Decimal ở server) — không parseFloat.
 * Tổng tiền LUÔN do server tính; FE chỉ hiển thị.
 */
import { apiDelete, apiDownload, apiGet, apiGetPaged, apiPatch, apiPost, saveBlob } from '@/lib/api';
import type { Quotation, QuotationItem, QuotationStatus } from '@/types';

export interface QuotationFilters {
  q?: string;
  status?: string;
  intake_id?: string;
  page?: number;
  limit?: number;
}
export function listQuotations(f: QuotationFilters = {}) {
  return apiGetPaged<Quotation[]>('/quotations', { ...f });
}
export function getQuotation(id: string) {
  return apiGet<Quotation>(`/quotations/${id}`);
}

export interface QuotationBody {
  intake_id?: string | null;
  customer_name: string;
  customer_address?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  issue_date?: string | null;
  valid_until?: string | null;
  vat_rate?: string | null;
  note?: string | null;
  items: QuotationItem[];
}
export function createQuotation(body: QuotationBody) {
  return apiPost<Quotation>('/quotations', body);
}
/** Tạo báo giá tự động từ các chỉ tiêu đã phân của phiếu nhận mẫu. */
export function createQuotationFromIntake(intakeId: string) {
  return apiPost<Quotation>(`/quotations/from-intake/${intakeId}`, {});
}
export function updateQuotation(id: string, body: Partial<QuotationBody>) {
  return apiPatch<Quotation>(`/quotations/${id}`, body);
}
export function changeQuotationStatus(id: string, status: QuotationStatus) {
  return apiPost<Quotation>(`/quotations/${id}/status`, { status });
}
export function deleteQuotation(id: string) {
  return apiDelete(`/quotations/${id}`);
}

/** Tải BẢNG BÁO GIÁ (.xlsx) đúng layout mẫu của Viện. */
export async function exportQuotationXlsx(id: string) {
  const { blob, filename } = await apiDownload(`/quotations/${id}/export.xlsx`);
  saveBlob(blob, filename);
}
