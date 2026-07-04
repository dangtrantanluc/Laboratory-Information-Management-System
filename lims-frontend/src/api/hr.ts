import { apiGet, apiGetPaged, apiPatch, apiPost, apiUpload } from '@/lib/api';
import type {
  CatalogItem,
  Competence,
  CompetenceKind,
  CompetenceSummary,
  HrProfile,
  SalaryHistoryItem,
} from '@/types';

// ── Hồ sơ nhân sự ───────────────────────────────────────────────
export interface HrProfileFilters {
  q?: string;
  department_id?: string;
  job_title?: string;
  contract_expiring_within_days?: number;
  salary_raise_within_days?: number;
  page?: number;
  limit?: number;
}
export function listProfiles(f: HrProfileFilters = {}) {
  return apiGetPaged<HrProfile[]>('/hr-profiles', { ...f });
}
export function getMyProfile() {
  return apiGet<HrProfile>('/hr-profiles/me');
}
export function getProfile(userId: string) {
  return apiGet<HrProfile>(`/hr-profiles/${userId}`);
}

export interface CreateProfileBody {
  user_id: string;
  job_title: string;
  hired_date?: string | null;
  phone?: string | null;
}
export function createProfile(body: CreateProfileBody) {
  return apiPost<HrProfile>('/hr-profiles', body);
}

export interface UpdateProfileBody {
  job_title?: string | null;
  hired_date?: string | null;
  phone?: string | null;
  position?: string | null;
}
export function updateProfile(userId: string, body: UpdateProfileBody) {
  return apiPatch<HrProfile>(`/hr-profiles/${userId}`, body);
}

// ── Hợp đồng ────────────────────────────────────────────────────
export interface UpdateContractBody {
  contract_signed_date: string;
  contract_type: string;
  contract_end_date?: string | null;
}
export function updateContract(userId: string, body: UpdateContractBody) {
  return apiPatch<HrProfile>(`/hr-profiles/${userId}/contract`, body);
}

// ── Chu kỳ nâng lương ───────────────────────────────────────────
export function updateSalaryCycle(userId: string, salary_cycle_years: number) {
  return apiPatch<HrProfile>(`/hr-profiles/${userId}/salary-cycle`, { salary_cycle_years });
}

// ── Nâng lương + lịch sử ────────────────────────────────────────
export interface CreateSalaryRaiseBody {
  salary_grade: string;
  salary_coefficient: string;
  base_salary_amount: string;
  raise_date: string;
  note?: string | null;
}
export function createSalaryRaise(userId: string, body: CreateSalaryRaiseBody) {
  return apiPost<HrProfile & { salary_history_id?: string }>(
    `/hr-profiles/${userId}/salary-raises`,
    body,
  );
}
export function listSalaryHistory(userId: string, page = 1, limit = 50) {
  return apiGetPaged<SalaryHistoryItem[]>(`/hr-profiles/${userId}/salary-history`, { page, limit });
}

// ── Hồ sơ năng lực ──────────────────────────────────────────────
export function listCompetences(userId: string, filters: { kind?: string; status?: string } = {}) {
  return apiGet<Competence[]>(`/hr-profiles/${userId}/competences`, { ...filters });
}
export interface CreateCompetenceBody {
  kind: CompetenceKind;
  title: string;
  issuer?: string | null;
  issued_date?: string | null;
  expiry_date?: string | null;
  scope_detail?: string | null;
  authorized_by?: string | null;
}
export function createCompetence(userId: string, body: CreateCompetenceBody) {
  return apiPost<Competence>(`/hr-profiles/${userId}/competences`, body);
}
export function updateCompetence(competenceId: string, body: Partial<CreateCompetenceBody>) {
  return apiPatch<Competence>(`/competences/${competenceId}`, body);
}
export function uploadCompetenceAttachment(competenceId: string, file: File) {
  return apiUpload<{ attachment_id: string; owner_type: string; file_name: string }>(
    `/competences/${competenceId}/attachments`,
    file,
  );
}

export function getCompetenceSummary(userId: string) {
  return apiGet<CompetenceSummary>(`/hr-profiles/${userId}/competence-summary`);
}

// ── Danh mục ────────────────────────────────────────────────────
export function listContractTypes() {
  return apiGet<CatalogItem[]>('/catalogs/contract-types');
}
