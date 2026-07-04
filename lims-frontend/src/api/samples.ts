import { apiDownload, apiGet, apiGetPaged, apiPatch, apiPost, apiDelete, saveBlob } from '@/lib/api';
import type {
  Assignment,
  AssignmentResult,
  CustodyEntry,
  OverdueSample,
  RequestSample,
  SampleDetail,
  SampleListItem,
  SampleResultItem,
  TestRequestDetail,
  TestRequestListItem,
} from '@/types';

// ── Test requests ───────────────────────────────────────────────
export interface RequestFilters {
  q?: string;
  department_id?: string;
  customer_id?: string;
  received_from?: string;
  received_to?: string;
  status?: string;
  page?: number;
  limit?: number;
}
export function listRequests(f: RequestFilters = {}) {
  return apiGetPaged<TestRequestListItem[]>('/test-requests', { ...f });
}
export function getRequest(id: string) {
  return apiGet<TestRequestDetail>(`/test-requests/${id}`);
}
export interface CreateRequestBody {
  customer_id?: string | null;
  sender_name: string;
  department_id?: string | null;
  received_by?: string | null;
  received_at?: string | null;
  note?: string | null;
}
export function createRequest(body: CreateRequestBody) {
  return apiPost<TestRequestListItem>('/test-requests', body);
}
export function updateRequest(id: string, body: Partial<CreateRequestBody>) {
  return apiPatch<TestRequestDetail>(`/test-requests/${id}`, body);
}
export function listRequestSamples(id: string) {
  return apiGetPaged<RequestSample[]>(`/test-requests/${id}/samples`);
}
export interface AddSampleBody {
  description: string;
  deadline_at: string;
  condition_status?: string | null;
  condition_note?: string | null;
}
export function addSample(requestId: string, body: AddSampleBody) {
  return apiPost<RequestSample>(`/test-requests/${requestId}/samples`, body);
}

// ── Samples ─────────────────────────────────────────────────────
export interface SampleFilters {
  q?: string;
  status?: string;
  department_id?: string;
  assigned_to?: string;
  request_id?: string;
  deadline_from?: string;
  deadline_to?: string;
  overdue_only?: boolean;
  page?: number;
  limit?: number;
}
export function listSamples(f: SampleFilters = {}) {
  return apiGetPaged<SampleListItem[]>('/samples', { ...f });
}
export function getSample(id: string) {
  return apiGet<SampleDetail>(`/samples/${id}`);
}
export function updateSample(id: string, body: { description?: string }) {
  return apiPatch<SampleDetail>(`/samples/${id}`, body);
}
export function updateCondition(id: string, condition_status: string, condition_note?: string) {
  return apiPatch(`/samples/${id}/condition`, { condition_status, condition_note });
}
export function updateDeadline(id: string, deadline_at: string) {
  return apiPatch(`/samples/${id}/deadline`, { deadline_at });
}

export function listAssignments(sampleId: string) {
  return apiGet<Assignment[]>(`/samples/${sampleId}/assignments`);
}
export function createAssignment(sampleId: string, part_name: string, assigned_to: string) {
  return apiPost<Assignment>(`/samples/${sampleId}/assignments`, { part_name, assigned_to });
}
export function cancelAssignment(assignmentId: string) {
  return apiDelete(`/assignments/${assignmentId}`);
}

export function createHandover(sampleId: string, to_user: string, reason: string) {
  return apiPost(`/samples/${sampleId}/handovers`, { to_user, reason });
}
export function getCustodyChain(sampleId: string) {
  return apiGet<CustodyEntry[]>(`/samples/${sampleId}/custody-chain`);
}

export function getAssignmentResult(assignmentId: string) {
  return apiGet<AssignmentResult | null>(`/assignments/${assignmentId}/results`);
}
export function enterResult(assignmentId: string, result_data: Record<string, unknown>, note?: string) {
  return apiPost(`/assignments/${assignmentId}/results`, { result_data, note });
}
export function approveResult(resultId: string, note?: string) {
  return apiPost(`/results/${resultId}/approve`, { note });
}
export function returnResult(resultId: string, reason: string) {
  return apiPost(`/results/${resultId}/return`, { reason });
}
export function reviseResult(resultId: string, result_data: Record<string, unknown>, reason: string) {
  return apiPost(`/results/${resultId}/revisions`, { result_data, reason });
}
export function getSampleResults(sampleId: string) {
  return apiGet<{ sample_id: string; sample_code: string; results: SampleResultItem[] }>(
    `/samples/${sampleId}/results`,
  );
}

export function finalizeSample(sampleId: string, note?: string) {
  return apiPost(`/samples/${sampleId}/finalize`, { note });
}
export function addOverdueReason(sampleId: string, reason: string) {
  return apiPost(`/samples/${sampleId}/overdue-reasons`, { reason });
}
export function listOverdue(params: { mode?: string; within_days?: number; department_id?: string; page?: number; limit?: number } = {}) {
  return apiGetPaged<OverdueSample[]>('/samples/overdue', { ...params });
}

export async function exportResultReport(sampleId: string, sampleCode: string) {
  const { blob, filename } = await apiDownload(`/samples/${sampleId}/result-report.pdf`);
  saveBlob(blob, filename || `result-${sampleCode}.pdf`);
}
