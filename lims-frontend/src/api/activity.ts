import { apiDelete, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type {
  ResearchContract,
  StaffActivity,
  StaffActivityKind,
  TrainingCertificate,
} from '@/types';

// ── Hợp đồng NCKH ───────────────────────────────────────────────
export interface ContractFilters {
  q?: string;
  academic_year?: string;
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listContracts(f: ContractFilters = {}) {
  return apiGetPaged<ResearchContract[]>('/research-contracts', { ...f });
}
export interface ContractBody {
  title: string;
  contract_type?: string | null;
  value_amount?: string | null;
  currency?: string | null;
  partner_org?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  academic_year?: string | null;
  department_id?: string | null;
}
export function createContract(body: ContractBody) {
  return apiPost<ResearchContract>('/research-contracts', body);
}
export function updateContract(id: string, body: Partial<ContractBody>) {
  return apiPatch<ResearchContract>(`/research-contracts/${id}`, body);
}
export function deleteContract(id: string) {
  return apiDelete(`/research-contracts/${id}`);
}

// ── Công tác khác ───────────────────────────────────────────────
export interface ActivityFilters {
  kind?: StaffActivityKind;
  academic_year?: string;
  page?: number;
  limit?: number;
}
export function listActivities(f: ActivityFilters = {}) {
  return apiGetPaged<StaffActivity[]>('/staff-activities', { ...f });
}
export interface ActivityBody {
  kind: StaffActivityKind;
  content: string;
  performed_at?: string | null;
  academic_year?: string | null;
  performer_user_id?: string | null;
  department_id?: string | null;
}
export function createActivity(body: ActivityBody) {
  return apiPost<StaffActivity>('/staff-activities', body);
}
export function updateActivity(id: string, body: Partial<ActivityBody>) {
  return apiPatch<StaffActivity>(`/staff-activities/${id}`, body);
}
export function deleteActivity(id: string) {
  return apiDelete(`/staff-activities/${id}`);
}

// ── Chứng nhận đào tạo (cấp GCN) ────────────────────────────────
export interface CertificateFilters {
  q?: string;
  academic_year?: string;
  page?: number;
  limit?: number;
}
export function listCertificates(f: CertificateFilters = {}) {
  return apiGetPaged<TrainingCertificate[]>('/training-certificates', { ...f });
}
export interface CertificateBody {
  recipient_name: string;
  certificate_no?: string | null;
  course_name?: string | null;
  issued_date?: string | null;
  note?: string | null;
  academic_year?: string | null;
  host_user_id?: string | null;
  department_id?: string | null;
}
export function createCertificate(body: CertificateBody) {
  return apiPost<TrainingCertificate>('/training-certificates', body);
}
export function updateCertificate(id: string, body: Partial<CertificateBody>) {
  return apiPatch<TrainingCertificate>(`/training-certificates/${id}`, body);
}
export function deleteCertificate(id: string) {
  return apiDelete(`/training-certificates/${id}`);
}
