/**
 * M6 — Báo cáo & Dashboard (Reporting & Analytics).
 * Tầng tổng hợp READ-ONLY: dashboard KPI + charts + báo cáo mẫu/hóa chất + thống kê truy cập R15
 * + xuất Excel/PDF + ghi lượt xem trang (page-view).
 * RBAC enforce ở backend — FE chỉ hiển thị khối có trong response (`'samples' in data`).
 * Số tiền là number (KPI đếm/tổng) — hiển thị qua formatNumber, KHÔNG tính tiếp.
 */
import { apiDownload, request, saveBlob } from '@/lib/api';
import type {
  DashboardChartsResponse,
  DashboardCharts,
  DashboardData,
  DashboardMeta,
  DashboardResponse,
  ChemicalsReportData,
  ChemicalsReportResponse,
  ReportType,
  SamplesReportData,
  SamplesReportResponse,
  SystemAccessData,
  SystemAccessResponse,
  SystemAccessUserData,
} from '@/types';

/** Bộ lọc thời gian thống nhất (§0.6). Khoảng nửa mở [from, to). */
export interface ReportFilters {
  from?: string;
  to?: string;
  department_id?: string;
  group_by?: 'day' | 'week' | 'month';
}

/** Helper lấy cả data + meta (aggregate có generated_at/cached, không phải PageMeta). */
async function getAggregate<D, M>(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): Promise<{ data: D; meta: M }> {
  const res = await request<D>(path, { method: 'GET', query });
  return { data: res.data, meta: (res.meta as unknown as M) ?? ({} as M) };
}

// ── #1 Dashboard tổng hợp ───────────────────────────────────────
export function getDashboard(params: { department_id?: string; due_within_days?: number } = {}) {
  return getAggregate<DashboardData, DashboardMeta>('/dashboard', { ...params }) as Promise<DashboardResponse>;
}

// ── #2 Charts ───────────────────────────────────────────────────
export function getDashboardCharts(
  params: ReportFilters & { charts?: string } = {},
) {
  return getAggregate<DashboardCharts, DashboardMeta>('/dashboard/charts', {
    ...params,
  }) as Promise<DashboardChartsResponse>;
}

// ── #3 Báo cáo mẫu ──────────────────────────────────────────────
export interface SamplesReportFilters extends ReportFilters {
  status?: string;
  time_field?: 'received_at' | 'completed_at';
  breakdown?: 'status' | 'time' | 'department';
}
export function getSamplesReport(params: SamplesReportFilters = {}) {
  return getAggregate<SamplesReportData, DashboardMeta>('/reports/samples', {
    ...params,
  }) as Promise<SamplesReportResponse>;
}

// ── #4 Báo cáo hóa chất ─────────────────────────────────────────
export interface ChemicalsReportFilters extends ReportFilters {
  type?: 'mass' | 'volume' | 'count';
  chemical_id?: string;
  metric?: 'consumption' | 'stock';
}
export function getChemicalsReport(params: ChemicalsReportFilters = {}) {
  return getAggregate<ChemicalsReportData, DashboardMeta>('/reports/chemicals', {
    ...params,
  }) as Promise<ChemicalsReportResponse>;
}

// ── #10 Thống kê truy cập hệ thống (R15) ────────────────────────
export interface SystemAccessFilters {
  from?: string;
  to?: string;
  group_by?: 'day' | 'week' | 'month';
  user_id?: string;
  action_type?: 'access' | 'download' | 'edit' | 'all';
  top_n?: number;
  include_timeline?: boolean;
}
export function getSystemAccess(params: SystemAccessFilters = {}) {
  return getAggregate<SystemAccessData, DashboardMeta>('/reports/system-access', {
    ...params,
  }) as Promise<SystemAccessResponse>;
}

// ── #11 Chi tiết 1 user ─────────────────────────────────────────
export function getSystemAccessUser(
  userId: string,
  params: { from?: string; to?: string; recent_actions?: number } = {},
) {
  return getAggregate<SystemAccessUserData, DashboardMeta>(
    `/reports/system-access/users/${userId}`,
    { ...params },
  );
}

// ── #12/#13 Xuất Excel / PDF ────────────────────────────────────
export type ExportParams = Record<string, string | number | boolean | undefined | null>;

export async function exportReportXlsx(reportType: ReportType, params: ExportParams = {}) {
  const { blob, filename } = await apiDownload(`/reports/${reportType}/export.xlsx`, { ...params });
  saveBlob(blob, filename);
}

export async function exportReportPdf(reportType: ReportType, params: ExportParams = {}) {
  const { blob, filename } = await apiDownload(`/reports/${reportType}/export.pdf`, { ...params });
  saveBlob(blob, filename);
}

// ── #14 Ghi lượt xem trang (best-effort, không chặn UI) ─────────
export async function trackPageView(path: string): Promise<void> {
  try {
    await request<void>('/analytics/page-view', { method: 'POST', body: { path } });
  } catch {
    /* best-effort — lỗi bỏ qua, không chặn UI (BR-RPT-013) */
  }
}
