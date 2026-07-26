import { apiDelete, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type { LabAccessCard } from '@/types';

export interface LabAccessCardFilters {
  q?: string;
  supervisor_name?: string;
  room?: string;
  active_on?: string;
  page?: number;
  limit?: number;
}
export function listLabAccessCards(f: LabAccessCardFilters = {}) {
  return apiGetPaged<LabAccessCard[]>('/lab-access-cards', { ...f });
}

export interface LabAccessCardBody {
  student_name?: string;
  class_name?: string | null;
  student_code?: string;
  email?: string | null;
  room?: string;
  purpose?: string | null;
  supervisor_name?: string | null;
  valid_from?: string;
  valid_to?: string | null;
  note?: string | null;
}
export function createLabAccessCard(body: LabAccessCardBody) {
  return apiPost<LabAccessCard>('/lab-access-cards', body);
}
export function updateLabAccessCard(id: string, body: LabAccessCardBody) {
  return apiPatch<LabAccessCard>(`/lab-access-cards/${id}`, body);
}
export function deleteLabAccessCard(id: string) {
  return apiDelete(`/lab-access-cards/${id}`);
}
