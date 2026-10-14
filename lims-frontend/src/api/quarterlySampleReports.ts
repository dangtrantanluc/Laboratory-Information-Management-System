/**
 * Báo cáo mẫu phân tích theo quý (m54) — lab nhập, Văn phòng tổng hợp và xuất Excel.
 *
 * Kiểu dữ liệu để ngay tại đây thay vì types/index.ts (file đó đã vượt trần kích thước).
 */
import { apiDelete, apiDownload, apiGet, apiPost, apiPut, saveBlob } from '@/lib/api';
import type { TestMatrix } from '@/types';

export type QuarterlyReportStatus = 'draft' | 'submitted' | 'returned' | 'locked';

export interface QuarterlyReportItem {
  id: string;
  sample_code: string;
  received_date: string;
  matrix: TestMatrix;
  matrix_label: string;
  matrix_other: string | null;
  quantity: number;
  criteria: { test_parameter_id: string | null; name: string }[];
  extra_criteria: string | null;
  criteria_text: string;
  note: string | null;
  created_by_name: string | null;
  updated_at: string;
}

export interface QuarterlyReport {
  id: string;
  department_id: string;
  department_name: string;
  department_code: string;
  year: number;
  quarter: number;
  status: QuarterlyReportStatus;
  status_label: string;
  lab_note: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  returned_by_name: string | null;
  returned_at: string | null;
  return_reason: string | null;
  locked_by_name: string | null;
  locked_at: string | null;
  item_count: number;
  total_quantity: number;
  items: QuarterlyReportItem[];
  can_edit: boolean;
  can_review: boolean;
}

export interface DepartmentRef {
  id: string;
  name: string;
  code: string;
}

export interface CurrentQuarterlyReport {
  department: DepartmentRef;
  year: number;
  quarter: number;
  report: QuarterlyReport | null;
  can_edit: boolean;
}

export interface QuarterlyOverviewRow {
  department: DepartmentRef;
  report_id: string | null;
  status: QuarterlyReportStatus | null;
  status_label: string;
  item_count: number;
  total_quantity: number;
  submitted_at: string | null;
  locked_at: string | null;
}

export interface QuarterlyItemBody {
  sample_code: string;
  received_date: string;
  matrix: TestMatrix;
  matrix_other: string | null;
  quantity: number;
  test_parameter_ids: string[];
  extra_criteria: string | null;
  note: string | null;
}

const BASE = '/quarterly-sample-reports';

export function getOverview(year: number, quarter: number) {
  return apiGet<QuarterlyOverviewRow[]>(`${BASE}/overview`, { year, quarter });
}
export function getCurrent(year: number, quarter: number, departmentId?: string) {
  return apiGet<CurrentQuarterlyReport>(`${BASE}/current`, {
    year,
    quarter,
    department_id: departmentId,
  });
}
export function getReport(id: string) {
  return apiGet<QuarterlyReport>(`${BASE}/${id}`);
}
/** Lấy hoặc lập báo cáo quý của phòng mình — gọi lại vẫn chỉ một bản. */
export function ensureReport(year: number, quarter: number) {
  return apiPost<QuarterlyReport>(BASE, { year, quarter });
}
export function createItem(reportId: string, body: QuarterlyItemBody) {
  return apiPost<QuarterlyReportItem>(`${BASE}/${reportId}/items`, body);
}
/** Nhập nhiều mẫu một lần — có dòng lỗi thì không lưu gì; lỗi theo dòng nằm ở ApiError.details. */
export function createItemsBatch(reportId: string, items: QuarterlyItemBody[]) {
  return apiPost<QuarterlyReport>(`${BASE}/${reportId}/items/batch`, { items });
}
export interface BatchRowError {
  row: number;
  sample_code: string | null;
  message: string;
}
export function updateItem(reportId: string, itemId: string, body: QuarterlyItemBody) {
  return apiPut<QuarterlyReportItem>(`${BASE}/${reportId}/items/${itemId}`, body);
}
export function deleteItem(reportId: string, itemId: string) {
  return apiDelete(`${BASE}/${reportId}/items/${itemId}`);
}
export function submitReport(reportId: string, body: { lab_note?: string | null; confirm_empty?: boolean }) {
  return apiPost<QuarterlyReport>(`${BASE}/${reportId}/submit`, body);
}
export function returnReport(reportId: string, reason: string) {
  return apiPost<QuarterlyReport>(`${BASE}/${reportId}/return`, { reason });
}
export function lockReport(reportId: string) {
  return apiPost<QuarterlyReport>(`${BASE}/${reportId}/lock`);
}
export function reopenReport(reportId: string, reason: string) {
  return apiPost<QuarterlyReport>(`${BASE}/${reportId}/reopen`, { reason });
}
export async function exportQuarterlyReports(year: number, quarter: number, includeUnlocked: boolean) {
  const { blob, filename } = await apiDownload(`${BASE}/export.xlsx`, {
    year,
    quarter,
    include_unlocked: includeUnlocked || undefined,
  });
  saveBlob(blob, filename);
}

// ── Thống kê (tab ở trang Báo cáo & Thống kê) ───────────────────
export interface QuarterlyStats {
  year: number;
  quarter: number | null;
  include_unlocked: boolean;
  departments: DepartmentRef[];
  reports: { department_id: string; quarter: number; status: QuarterlyReportStatus; status_label: string }[];
  /** Ô phẳng phòng × quý × loại mẫu — giao diện tự cộng theo chiều cần xem. */
  cells: {
    department_id: string;
    quarter: number;
    matrix: TestMatrix;
    matrix_label: string;
    items: number;
    quantity: number;
  }[];
  top_criteria: { name: string; items: number }[];
}
export function getStats(params: {
  year: number;
  quarter?: number;
  department_id?: string;
  include_unlocked?: boolean;
}) {
  return apiGet<QuarterlyStats>(`${BASE}/stats`, {
    ...params,
    include_unlocked: params.include_unlocked || undefined,
  });
}

// ── Tiện ích quý ────────────────────────────────────────────────
export const ROMAN = ['', 'I', 'II', 'III', 'IV'];

export function currentQuarter(d = new Date()): { year: number; quarter: number } {
  return { year: d.getFullYear(), quarter: Math.floor(d.getMonth() / 3) + 1 };
}

/** Ngày đầu / cuối quý dạng YYYY-MM-DD — giới hạn ô chọn ngày nhận mẫu. */
export function quarterBounds(year: number, quarter: number): { start: string; end: string } {
  const pad = (n: number) => String(n).padStart(2, '0');
  const startMonth = 3 * (quarter - 1) + 1;
  const endMonth = startMonth + 2;
  const lastDay = new Date(year, endMonth, 0).getDate();
  return { start: `${year}-${pad(startMonth)}-01`, end: `${year}-${pad(endMonth)}-${pad(lastDay)}` };
}

export function periodLabel(year: number, quarter: number) {
  return `Quý ${ROMAN[quarter]}/${year}`;
}
