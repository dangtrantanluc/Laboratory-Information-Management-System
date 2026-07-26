/**
 * Nhận & Chuyển mẫu (GĐ2b).
 * - Phiếu nhận (intake): reception tạo/sửa; đính kèm form qua /attachments owner 'sample_intake'.
 * - Phiếu chuyển (dispatch): reception thêm chỉ tiêu + phòng lab → notify lab; lab đổi status → notify reception.
 */
import { apiDelete, apiGet, apiGetPaged, apiPatch, apiPost, apiUploadForm } from '@/lib/api';
import type {
  CustomerInfoRequest, DispatchStatus, IntakeStatus, PaymentStatus,
  SampleDispatch, SampleIntake, TestParameter,
} from '@/types';

export interface IntakeFilters {
  q?: string;
  status?: string;
  page?: number;
  limit?: number;
}
export function listIntakes(f: IntakeFilters = {}) {
  return apiGetPaged<SampleIntake[]>('/intakes', { ...f });
}
export function getIntake(id: string) {
  return apiGet<SampleIntake>(`/intakes/${id}`);
}
export interface IntakeBody {
  customer_name: string;
  contact?: string | null;
  description?: string | null;
  note?: string | null;
  address?: string | null;
  tax_code?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  due_date?: string | null;
  result_language?: string | null;
  return_method?: string | null;
  fee_note?: string | null;
  other_request?: string | null;
}
export function createIntake(body: IntakeBody) {
  return apiPost<SampleIntake>('/intakes', body);
}
export function updateIntake(id: string, body: Partial<IntakeBody> & { status?: string }) {
  return apiPatch<SampleIntake>(`/intakes/${id}`, body);
}

// ── m28: Trạng thái phiếu + thanh toán ──────────────────────────
export function changeIntakeStatus(id: string, status: IntakeStatus, note?: string) {
  return apiPost<SampleIntake>(`/intakes/${id}/status`, { status, note: note || null });
}
export interface PaymentBody {
  payment_status?: PaymentStatus;
  paid_amount?: string | null;
  payment_date?: string | null;
  payment_ref?: string | null;
  payment_note?: string | null;
}
export function updateIntakePayment(id: string, body: PaymentBody) {
  return apiPatch<SampleIntake>(`/intakes/${id}/payment`, body);
}

export function addDispatch(
  intakeId: string,
  body: {
    chi_tieu?: string | null;
    /** m27: chọn từ danh mục chỉ tiêu (khi có, backend tự lấy tên/phương pháp/đơn giá). */
    test_parameter_id?: string | null;
    sample_name?: string | null;
    quantity?: number | null;
    target_department_id: string;
    note?: string | null;
    don_vi?: string | null;
    phuong_phap?: string | null;
  },
) {
  return apiPost<SampleDispatch>(`/intakes/${intakeId}/dispatches`, body);
}

/** m27: chuyển NHIỀU chỉ tiêu cùng lúc (nguyên tử, gộp thông báo theo phòng). */
export interface DispatchItemBody {
  chi_tieu?: string | null;
  test_parameter_id?: string | null;
  sample_name?: string | null;
  quantity?: number | null;
  target_department_id: string;
  note?: string | null;
  don_vi?: string | null;
  phuong_phap?: string | null;
}
export function addDispatchesBatch(intakeId: string, items: DispatchItemBody[]) {
  return apiPost<SampleDispatch[]>(`/intakes/${intakeId}/dispatches/batch`, { items });
}

export function listDispatches(f: { status?: string; page?: number; limit?: number } = {}) {
  return apiGetPaged<SampleDispatch[]>('/dispatches', { ...f });
}
export function getDispatch(id: string) {
  return apiGet<SampleDispatch>(`/dispatches/${id}`);
}
export interface DispatchUpdate {
  status?: DispatchStatus;
  /** m28 — BM 7.1.02 */
  sample_name?: string | null;
  quantity?: number | null;
  note?: string | null;
  don_vi?: string | null;
  phuong_phap?: string | null;
  ket_qua?: string | null;
  can_bo?: string | null;
}
export function updateDispatch(id: string, body: DispatchUpdate) {
  return apiPatch<SampleDispatch>(`/dispatches/${id}`, body);
}

/** Đính kèm file (phiếu nhận/chuyển) qua endpoint generic /attachments. */
export function uploadIntakeFile(
  ownerType: 'sample_intake' | 'sample_dispatch',
  ownerId: string,
  file: File,
) {
  return apiUploadForm('/attachments', { owner_type: ownerType, owner_id: ownerId, file });
}

export async function openFile(fileId: string) {
  const data = await apiGet<{ download_url: string }>(`/attachments/${fileId}`);
  if (data?.download_url) window.open(data.download_url, '_blank', 'noopener');
}

// ── m26: Xin xem thông tin khách hàng (khối lab → Phòng nhận mẫu) ──
export function createInfoRequest(intakeId: string, reason?: string) {
  return apiPost<CustomerInfoRequest>(`/intakes/${intakeId}/info-requests`, { reason: reason || null });
}
export function listInfoRequests(f: { status?: string; intake_id?: string; page?: number; limit?: number } = {}) {
  return apiGetPaged<CustomerInfoRequest[]>('/customer-info-requests', { ...f });
}
export function approveInfoRequest(id: string, note?: string) {
  return apiPost<CustomerInfoRequest>(`/customer-info-requests/${id}/approve`, { note: note || null });
}
export function rejectInfoRequest(id: string, note?: string) {
  return apiPost<CustomerInfoRequest>(`/customer-info-requests/${id}/reject`, { note: note || null });
}

// ── m27: Master data chỉ tiêu thử nghiệm ────────────────────────
export interface TestParameterFilters {
  q?: string;
  matrix?: string;
  department_id?: string;
  is_active?: boolean;
  unassigned?: boolean;
  page?: number;
  limit?: number;
}
export function listTestParameters(f: TestParameterFilters = {}) {
  return apiGetPaged<TestParameter[]>('/test-parameters', { ...f });
}
export interface TestParameterBody {
  matrix: string;
  name: string;
  sample_matrix?: string | null;
  method?: string | null;
  unit?: string | null;
  unit_price?: string | null;
  currency?: string | null;
  turnaround_days?: number | null;
  in_charge?: string | null;
  note?: string | null;
  department_id?: string | null;
  is_accredited?: boolean;
  is_active?: boolean;
}
export function createTestParameter(body: TestParameterBody) {
  return apiPost<TestParameter>('/test-parameters', body);
}
export function updateTestParameter(id: string, body: Partial<TestParameterBody>) {
  return apiPatch<TestParameter>(`/test-parameters/${id}`, body);
}
export function deleteTestParameter(id: string) {
  return apiDelete(`/test-parameters/${id}`);
}
