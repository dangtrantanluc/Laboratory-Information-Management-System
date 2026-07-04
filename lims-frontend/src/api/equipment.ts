import { apiGet, apiGetPaged, apiPatch, apiPost, apiUploadForm } from '@/lib/api';
import type {
  CalibrationCycleUnit,
  CalibrationRecord,
  CalibrationResult,
  CalibrationStatus,
  EquipmentAttachment,
  EquipmentDetail,
  EquipmentDownloadInfo,
  EquipmentListItem,
  EquipmentStatus,
} from '@/types';

// ── Thiết bị (M5.1) ─────────────────────────────────────────────
export interface EquipmentFilters {
  q?: string;
  status?: EquipmentStatus | '';
  department_id?: string;
  responsible_user_id?: string;
  calibration_status?: CalibrationStatus | '';
  overdue?: boolean;
  page?: number;
  limit?: number;
}
export function listEquipments(f: EquipmentFilters = {}) {
  return apiGetPaged<EquipmentListItem[]>('/equipments', { ...f });
}

export interface CalibrationDueFilters {
  within_days?: number;
  department_id?: string;
  bucket?: 'overdue' | 'due_soon' | 'failed' | 'all';
  page?: number;
  limit?: number;
}
export function listCalibrationDue(f: CalibrationDueFilters = {}) {
  return apiGetPaged<EquipmentListItem[]>('/equipments/calibration-due', { ...f });
}

export function getEquipment(id: string) {
  return apiGet<EquipmentDetail>(`/equipments/${id}`);
}

export interface CreateEquipmentBody {
  name: string;
  location?: string | null;
  department_id?: string | null;
  responsible_user_id?: string | null;
  purchase_date?: string | null;
  status?: EquipmentStatus;
  calibration_cycle_value?: number | null;
  calibration_cycle_unit?: CalibrationCycleUnit | null;
}
export function createEquipment(body: CreateEquipmentBody) {
  return apiPost<EquipmentDetail>('/equipments', body);
}

export interface UpdateEquipmentBody {
  name?: string;
  location?: string | null;
  responsible_user_id?: string | null;
  purchase_date?: string | null;
  status?: EquipmentStatus;
  calibration_cycle_value?: number | null;
  calibration_cycle_unit?: CalibrationCycleUnit | null;
}
export function updateEquipment(id: string, body: UpdateEquipmentBody) {
  return apiPatch<EquipmentDetail>(`/equipments/${id}`, body);
}

// ── Tài liệu thiết bị ───────────────────────────────────────────
export interface AddAttachmentInput {
  file: File;
  doc_type?: 'manual' | 'image' | 'other';
}
export function addEquipmentAttachment(equipmentId: string, input: AddAttachmentInput) {
  return apiUploadForm<EquipmentAttachment>(`/equipments/${equipmentId}/attachments`, {
    file: input.file,
    doc_type: input.doc_type ?? undefined,
  });
}
export function getAttachmentDownload(equipmentId: string, attachmentId: string) {
  return apiGet<EquipmentDownloadInfo>(
    `/equipments/${equipmentId}/attachments/${attachmentId}/download`,
  );
}

// ── Hiệu chuẩn (M5.2 — bất biến) ────────────────────────────────
export interface CalibrationFilters {
  result?: CalibrationResult;
  page?: number;
  limit?: number;
}
export function listCalibrations(equipmentId: string, f: CalibrationFilters = {}) {
  return apiGetPaged<CalibrationRecord[]>(`/equipments/${equipmentId}/calibrations`, { ...f });
}

export interface CreateCalibrationInput {
  calibrated_at: string;
  result: CalibrationResult;
  provider?: string | null;
  next_due_date_override?: string | null;
  override_reason?: string | null;
  note?: string | null;
  correction_of?: string | null;
  cert?: File | null;
}
export function createCalibration(equipmentId: string, input: CreateCalibrationInput) {
  return apiUploadForm<CalibrationRecord>(`/equipments/${equipmentId}/calibrations`, {
    calibrated_at: input.calibrated_at,
    result: input.result,
    provider: input.provider ?? undefined,
    next_due_date_override: input.next_due_date_override ?? undefined,
    override_reason: input.override_reason ?? undefined,
    note: input.note ?? undefined,
    correction_of: input.correction_of ?? undefined,
    cert: input.cert ?? undefined,
  });
}

export function getCalibration(id: string) {
  return apiGet<CalibrationRecord>(`/calibrations/${id}`);
}
export function getCertDownload(calibrationId: string) {
  return apiGet<EquipmentDownloadInfo>(`/calibrations/${calibrationId}/cert/download`);
}

// ── Cron (CRON-5) ───────────────────────────────────────────────
export interface RunCalibrationDueResult {
  run_at: string;
  as_of_date: string;
  scanned_equipments: number;
  notifications_created: number;
  by_milestone: Record<string, number>;
  recipients: number;
  skipped_no_recipient: number;
  skipped_retired_or_no_cycle: number;
  deduped: number;
}
export function runCalibrationDueCron(as_of_date?: string) {
  return apiPost<RunCalibrationDueResult>('/admin/crons/equipment-calibration-due/run', {
    as_of_date: as_of_date ?? null,
  });
}
