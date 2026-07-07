import { apiGet, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type {
  ActionStatus,
  CapaEffectiveness,
  CapaType,
  NcDetail,
  NcListItem,
  NcSeverity,
  NcSource,
  NcStats,
  NcStatus,
} from '@/types';

// ── NC list (M8.1) ──────────────────────────────────────────────
export interface NcFilters {
  q?: string;
  status?: NcStatus | '';
  severity?: NcSeverity | '';
  source_type?: NcSource | '';
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listNonconformities(f: NcFilters = {}) {
  return apiGetPaged<NcListItem[]>('/nonconformities', { ...f });
}

export function getNcStats() {
  return apiGet<NcStats>('/nonconformities/stats');
}

export function getNonconformity(id: string) {
  return apiGet<NcDetail>(`/nonconformities/${id}`);
}

// ── Tạo / sửa NC ────────────────────────────────────────────────
export interface CreateNcBody {
  title: string;
  description: string;
  severity: NcSeverity;
  source_type?: NcSource;
  department_id?: string | null;
  impact_assessment?: string | null;
  affected_ref_type?: string | null;
}
export function createNonconformity(body: CreateNcBody) {
  return apiPost<NcDetail>('/nonconformities', body);
}

export interface UpdateNcBody {
  severity?: NcSeverity;
  impact_assessment?: string | null;
  affected_ref_type?: string | null;
}
export function updateNonconformity(id: string, body: UpdateNcBody) {
  return apiPatch<NcDetail>(`/nonconformities/${id}`, body);
}

export function cancelNonconformity(id: string, reason: string) {
  return apiPost<NcDetail>(`/nonconformities/${id}/cancel`, { reason });
}

// ── CAPA (M8.2 §8.7) ────────────────────────────────────────────
export interface OpenCapaBody {
  root_cause: string;
  owner_id: string;
  capa_type?: CapaType;
  due_date?: string | null;
}
export function openCapa(ncId: string, body: OpenCapaBody) {
  return apiPost<NcDetail>(`/nonconformities/${ncId}/capa`, body);
}

export interface AddActionBody {
  action: string;
  assignee_id?: string | null;
  due_date?: string | null;
}
export function addCapaAction(ncId: string, body: AddActionBody) {
  return apiPost<NcDetail>(`/nonconformities/${ncId}/actions`, body);
}

export function updateCapaAction(
  ncId: string,
  actionId: string,
  status: ActionStatus,
  note?: string,
) {
  return apiPatch<NcDetail>(`/nonconformities/${ncId}/actions/${actionId}`, { status, note });
}

export interface CloseCapaBody {
  effectiveness_result: CapaEffectiveness;
  effectiveness_note?: string | null;
}
export function closeCapa(ncId: string, body: CloseCapaBody) {
  return apiPost<NcDetail>(`/nonconformities/${ncId}/close`, body);
}

// ── Cron (CRON-7) ───────────────────────────────────────────────
export interface RunCapaDueResult {
  run_at: string;
  as_of_date: string;
  scanned_capa: number;
  notifications_created: number;
  by_milestone: Record<string, number>;
  deduped: number;
}
export function runCapaDueCron(as_of_date?: string) {
  return apiPost<RunCapaDueResult>('/admin/crons/capa-due/run', {
    as_of_date: as_of_date ?? null,
  });
}
