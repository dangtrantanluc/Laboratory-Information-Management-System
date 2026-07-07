import { apiGet, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type {
  ImprovementItem,
  ImprovementSource,
  ImprovementStatus,
  RiskBand,
  RiskDetail,
  RiskKind,
  RiskListItem,
  RiskStats,
  RiskStatus,
  TreatmentStatus,
} from '@/types';

// ── Risks (§8.5) ────────────────────────────────────────────────
export interface RiskFilters {
  q?: string;
  kind?: RiskKind | '';
  status?: RiskStatus | '';
  department_id?: string;
  band?: RiskBand | '';
  page?: number;
  limit?: number;
}
export function listRisks(f: RiskFilters = {}) {
  return apiGetPaged<RiskListItem[]>('/risks', { ...f });
}
export function getRiskStats() {
  return apiGet<RiskStats>('/risks/stats');
}
export function getRisk(id: string) {
  return apiGet<RiskDetail>(`/risks/${id}`);
}

export interface CreateRiskBody {
  title: string;
  context: string;
  likelihood: number;
  impact: number;
  kind?: RiskKind;
  process_ref?: string | null;
  owner_id?: string | null;
  department_id?: string | null;
  next_review_date?: string | null;
}
export function createRisk(body: CreateRiskBody) {
  return apiPost<RiskDetail>('/risks', body);
}

export interface UpdateRiskBody {
  title?: string;
  context?: string;
  likelihood?: number;
  impact?: number;
  process_ref?: string | null;
  status?: RiskStatus;
  owner_id?: string | null;
  next_review_date?: string | null;
}
export function updateRisk(id: string, body: UpdateRiskBody) {
  return apiPatch<RiskDetail>(`/risks/${id}`, body);
}

export interface AddTreatmentBody {
  treatment: string;
  owner_id?: string | null;
  due_date?: string | null;
}
export function addTreatment(riskId: string, body: AddTreatmentBody) {
  return apiPost<RiskDetail>(`/risks/${riskId}/treatments`, body);
}
export function updateTreatment(riskId: string, treatmentId: string, status: TreatmentStatus) {
  return apiPatch<RiskDetail>(`/risks/${riskId}/treatments/${treatmentId}`, { status });
}
export function closeRisk(riskId: string, note?: string) {
  return apiPost<RiskDetail>(`/risks/${riskId}/close`, { note: note ?? null });
}

export interface RunRiskReviewDueResult {
  run_at: string;
  as_of_date: string;
  scanned_risks: number;
  notifications_created: number;
  by_milestone: Record<string, number>;
  deduped: number;
}
export function runRiskReviewCron(as_of_date?: string) {
  return apiPost<RunRiskReviewDueResult>('/admin/crons/risk-review-due/run', {
    as_of_date: as_of_date ?? null,
  });
}

// ── Improvements (§8.6) ─────────────────────────────────────────
export interface ImprovementFilters {
  q?: string;
  status?: ImprovementStatus | '';
  source?: ImprovementSource | '';
  page?: number;
  limit?: number;
}
export function listImprovements(f: ImprovementFilters = {}) {
  return apiGetPaged<ImprovementItem[]>('/improvements', { ...f });
}
export function getImprovement(id: string) {
  return apiGet<ImprovementItem>(`/improvements/${id}`);
}
export interface CreateImprovementBody {
  title: string;
  description: string;
  source?: ImprovementSource;
  owner_id?: string | null;
  department_id?: string | null;
}
export function createImprovement(body: CreateImprovementBody) {
  return apiPost<ImprovementItem>('/improvements', body);
}
export interface UpdateImprovementBody {
  status?: ImprovementStatus;
  owner_id?: string | null;
  linked_nc_id?: string | null;
}
export function updateImprovement(id: string, body: UpdateImprovementBody) {
  return apiPatch<ImprovementItem>(`/improvements/${id}`, body);
}
