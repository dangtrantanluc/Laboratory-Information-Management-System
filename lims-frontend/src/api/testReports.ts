/**
 * Phiếu kết quả thử nghiệm (m46) — BM 7.8/01/RIBE.
 *
 * Module CHỨNG TỪ: tệp do Phòng nhận mẫu soạn ngoài hệ thống rồi tải lên. Ở đây theo
 * dõi bản nào đã ra khỏi Viện, lúc nào, ai chịu trách nhiệm, bản nào đã bị thay thế.
 *
 * Tải tệp về đi qua endpoint RIÊNG (không phải /attachments/{id}) vì mỗi lượt tải một
 * chứng từ đã trao khách đều phải để lại vết riêng — `revoke` dùng chính vết đó để
 * biết phải báo cho ai khi thu hồi.
 */
import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from '@/lib/api';
import type { DeliveryMethod, TestReport, TestReportFile } from '@/types';

export function listTestReports(intakeId: string) {
  return apiGet<TestReport[]>(`/intakes/${intakeId}/test-reports`);
}

export interface TestReportBody {
  /** Bỏ trống thì backend sinh theo mã phiếu nhận (26N323, rồi -2, -3 nếu trùng). */
  report_no?: string | null;
  title?: string | null;
  note?: string | null;
  issued_at?: string | null;
}

export function createTestReport(intakeId: string, body: TestReportBody) {
  return apiPost<TestReport>(`/intakes/${intakeId}/test-reports`, body);
}

export function updateTestReport(reportId: string, body: TestReportBody) {
  return apiPatch<TestReport>(`/test-reports/${reportId}`, body);
}

export function deleteTestReport(reportId: string) {
  return apiDelete(`/test-reports/${reportId}`);
}

/** Phát hành — từ đây tệp bị khoá, sửa nội dung phải tạo bản sửa đổi. */
export function issueTestReport(reportId: string, issuedAt?: string | null) {
  return apiPost<TestReport>(`/test-reports/${reportId}/issue`, {
    issued_at: issuedAt || null,
  });
}

export interface DeliverBody {
  delivery_method: DeliveryMethod;
  delivered_to?: string | null;
  delivered_at?: string | null;
  delivery_note?: string | null;
}

export function deliverTestReport(reportId: string, body: DeliverBody) {
  return apiPost<TestReport>(`/test-reports/${reportId}/deliver`, body);
}

export function revokeTestReport(reportId: string, reason: string) {
  return apiPost<TestReport>(`/test-reports/${reportId}/revoke`, { reason });
}

/** Bản sửa đổi = bản nháp mới version+1; bản cũ tự chuyển "Đã thu hồi". */
export function reviseTestReport(reportId: string, reason: string, reportNo?: string | null) {
  return apiPost<TestReport>(`/test-reports/${reportId}/revisions`, {
    reason,
    report_no: reportNo || null,
  });
}

export function uploadTestReportFile(reportId: string, file: File) {
  return apiUpload<TestReportFile>(`/test-reports/${reportId}/files`, file, 'file');
}

export function deleteTestReportFile(reportId: string, attachmentId: string) {
  return apiDelete(`/test-reports/${reportId}/files/${attachmentId}`);
}

/** Mở tệp trong tab mới bằng presigned URL. Lượt tải được ghi vào nhật ký (BR-13). */
export async function openTestReportFile(reportId: string, attachmentId: string) {
  const data = await apiGet<TestReportFile & { download_url: string }>(
    `/test-reports/${reportId}/files/${attachmentId}`,
  );
  if (data.download_url) window.open(data.download_url, '_blank', 'noopener');
}
