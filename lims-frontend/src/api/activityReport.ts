import { apiDelete, apiGet, apiGetPaged, apiPost } from '@/lib/api';
import type { ActivityReport } from '@/types';

// ── Báo cáo hoạt động hàng tháng (m25) ──────────────────────────
export interface ReportFilters {
  period?: string;
  department_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}
export function listReports(f: ReportFilters = {}) {
  return apiGetPaged<ActivityReport[]>('/activity-reports', { ...f });
}
export function getReport(id: string) {
  return apiGet<ActivityReport>(`/activity-reports/${id}`);
}

// ── Payload các section ─────────────────────────────────────────
export interface TeachingEntry {
  course_name: string;
  semester?: string | null;
  hk1_theory_hours?: number | null;
  hk1_practice_hours?: number | null;
  hk2_theory_hours?: number | null;
  hk2_practice_hours?: number | null;
  hk3_theory_hours?: number | null;
  hk3_practice_hours?: number | null;
  note?: string | null;
}
export interface ProjectEntry {
  title: string;
  level?: string | null;
  role?: string | null;
  task_status?: string | null;
  budget_amount?: string | null;
}
export type PubKind = 'domestic' | 'international' | 'conference';
export interface PublicationEntry {
  pub_kind: PubKind;
  title: string;
  journal?: string | null;
  year?: number | null;
  doi?: string | null;
  is_scie?: boolean | null;
  is_ssci?: boolean | null;
  is_scopus?: boolean | null;
  is_aci?: boolean | null;
}
export interface ContractEntry {
  title: string;
  contract_type?: string | null;
  value_amount?: string | null;
  partner_org?: string | null;
}
export type OtherKind = 'dang' | 'cong_doan' | 'vilas' | 'khac';
export interface OtherEntry {
  kind: OtherKind;
  content: string;
}

export interface CreateReportBody {
  period_label: string;
  period_year?: number | null;
  academic_year?: string | null;
  department_id?: string | null;
  note?: string | null;
  teaching: TeachingEntry[];
  projects: ProjectEntry[];
  publications: PublicationEntry[];
  contracts: ContractEntry[];
  activities: OtherEntry[];
}

export function createReport(body: CreateReportBody) {
  return apiPost<ActivityReport>('/activity-reports', body);
}
export function reviewReport(id: string) {
  return apiPost<ActivityReport>(`/activity-reports/${id}/review`, {});
}
export function deleteReport(id: string) {
  return apiDelete(`/activity-reports/${id}`);
}
