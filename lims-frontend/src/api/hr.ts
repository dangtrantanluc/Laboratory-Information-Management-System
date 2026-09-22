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
export function getProfile(profileId: string) {
  return apiGet<HrProfile>(`/hr-profiles/${profileId}`);
}

export interface CreateProfileBody {
  /** Tuỳ chọn — bỏ trống nếu người này chưa có tài khoản (m48). */
  user_id?: string | null;
  full_name: string;
  birth_year?: number | null;
  job_title: string;
  /** Phòng công tác ghi thẳng lên hồ sơ (m49) — không còn suy từ tài khoản. */
  department_id?: string | null;
  hired_date?: string | null;
  phone?: string | null;
}
export function createProfile(body: CreateProfileBody) {
  return apiPost<HrProfile>('/hr-profiles', body);
}

export interface UpdateProfileBody {
  job_title?: string | null;
  department_id?: string | null;
  hired_date?: string | null;
  phone?: string | null;
  position?: string | null;
}
export function updateProfile(profileId: string, body: UpdateProfileBody) {
  return apiPatch<HrProfile>(`/hr-profiles/${profileId}`, body);
}

// ── Hợp đồng ────────────────────────────────────────────────────
export interface UpdateContractBody {
  contract_signed_date: string;
  contract_type: string;
  contract_end_date?: string | null;
}
export function updateContract(profileId: string, body: UpdateContractBody) {
  return apiPatch<HrProfile>(`/hr-profiles/${profileId}/contract`, body);
}

// ── Chu kỳ nâng lương ───────────────────────────────────────────
export function updateSalaryCycle(profileId: string, salary_cycle_years: number) {
  return apiPatch<HrProfile>(`/hr-profiles/${profileId}/salary-cycle`, { salary_cycle_years });
}

// ── Nâng lương + lịch sử ────────────────────────────────────────
export interface CreateSalaryRaiseBody {
  salary_grade: string;
  salary_coefficient: string;
  base_salary_amount: string;
  raise_date: string;
  note?: string | null;
}
export function createSalaryRaise(profileId: string, body: CreateSalaryRaiseBody) {
  return apiPost<HrProfile & { salary_history_id?: string }>(
    `/hr-profiles/${profileId}/salary-raises`,
    body,
  );
}
export function listSalaryHistory(profileId: string, page = 1, limit = 50) {
  return apiGetPaged<SalaryHistoryItem[]>(`/hr-profiles/${profileId}/salary-history`, { page, limit });
}

// ── Hồ sơ năng lực ──────────────────────────────────────────────
export function listCompetences(profileId: string, filters: { kind?: string; status?: string } = {}) {
  return apiGet<Competence[]>(`/hr-profiles/${profileId}/competences`, { ...filters });
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
export function createCompetence(profileId: string, body: CreateCompetenceBody) {
  return apiPost<Competence>(`/hr-profiles/${profileId}/competences`, body);
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

export function getCompetenceSummary(profileId: string) {
  return apiGet<CompetenceSummary>(`/hr-profiles/${profileId}/competence-summary`);
}

// ── Danh mục ────────────────────────────────────────────────────
export function listContractTypes() {
  return apiGet<CatalogItem[]>('/catalogs/contract-types');
}


// ── m48: gắn hồ sơ nhân sự ↔ tài khoản ──────────────────────────
/** Hồ sơ CHƯA GẮN trùng tên với một tài khoản — để người duyệt chọn, không tự gắn. */
export function suggestProfilesForUser(userId: string) {
  return apiGet<ProfileSuggestion[]>(`/users/${userId}/profile-suggestions`);
}
export function linkProfileAccount(profileId: string, userId: string) {
  return apiPost<HrProfile>(`/hr-profiles/${profileId}/link`, { user_id: userId });
}
export function unlinkProfileAccount(profileId: string) {
  return apiPost<HrProfile>(`/hr-profiles/${profileId}/unlink`, {});
}

export interface ProfileSuggestion {
  id: string;
  full_name: string;
  birth_year?: number | null;
  job_title: string;
  contract_type?: string | null;
}
