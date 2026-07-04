import { apiDownload, apiGet, apiGetPaged, apiPatch, apiPost, apiUpload, saveBlob } from '@/lib/api';
import type {
  Chemical,
  LowStockItem,
  Lot,
  Stock,
  Transaction,
  TransactionType,
  Unit,
} from '@/types';

// ── Units ───────────────────────────────────────────────────────
export function listUnits(group?: string) {
  return apiGet<Unit[]>('/units', { group });
}

// ── Chemicals ───────────────────────────────────────────────────
export interface ChemicalFilters {
  q?: string;
  department_id?: string;
  status?: string;
  measurement_group?: string;
  has_stock?: boolean;
  page?: number;
  limit?: number;
}
export function listChemicals(f: ChemicalFilters = {}) {
  return apiGetPaged<Chemical[]>('/chemicals', { ...f });
}
export function getChemical(id: string) {
  return apiGet<Chemical>(`/chemicals/${id}`);
}
export interface CreateChemicalBody {
  name: string;
  cas_no?: string | null;
  manufacturer?: string | null;
  base_unit: string;
  hazard_code?: string | null;
  department_id?: string | null;
  reorder_threshold?: string | null;
}
export function createChemical(body: CreateChemicalBody) {
  return apiPost<Chemical>('/chemicals', body);
}
export function updateChemical(id: string, body: Partial<CreateChemicalBody>) {
  return apiPatch<Chemical>(`/chemicals/${id}`, body);
}
export function deactivateChemical(id: string) {
  return apiPost<{ id: string; status: string }>(`/chemicals/${id}/deactivate`);
}

// ── Lots ────────────────────────────────────────────────────────
export function listLots(chemicalId: string, display_unit?: string) {
  return apiGet<Lot[]>(`/chemicals/${chemicalId}/lots`, { display_unit });
}
export interface InitialIntake {
  qty_input: string;
  input_unit: string;
  unit_price?: string | null;
  currency?: string | null;
  note?: string | null;
}
export interface CreateLotBody {
  lot_no: string;
  received_at?: string | null;
  expiry_date?: string | null;
  recheck_date?: string | null;
  initial_intake?: InitialIntake | null;
}
export function createLot(chemicalId: string, body: CreateLotBody) {
  return apiPost<{ lot: Lot; transaction: Transaction | null }>(`/chemicals/${chemicalId}/lots`, body);
}
/** Tải file CoA của lô (GET /lots/{id}/coa) — trả presigned URL, mở tab mới. 404 nếu chưa có CoA. */
export async function downloadLotCoa(lotId: string, _lotNo: string) {
  const info = await apiGet<{ download_url: string }>(`/lots/${lotId}/coa`);
  if (info?.download_url) window.open(info.download_url, '_blank', 'noopener');
}
/** Upload/ghi đè CoA cho lô (POST /lots/{id}/coa, multipart field 'file'). */
export function uploadLotCoa(lotId: string, file: File) {
  return apiUpload<{ lot_id: string; has_coa: boolean; file_name: string }>(
    `/lots/${lotId}/coa`,
    file,
  );
}
export function getStock(chemicalId: string, display_unit?: string) {
  return apiGet<Stock>(`/chemicals/${chemicalId}/stock`, { display_unit });
}
export function getFefo(chemicalId: string, display_unit?: string) {
  return apiGet<
    {
      lot_id: string;
      lot_no: string;
      qty_display: string;
      display_unit: string;
      expiry_date: string;
      is_expired: boolean;
      recheck_result: string | null;
      fefo_rank: number;
      requires_warning_confirm: boolean;
    }[]
  >(`/chemicals/${chemicalId}/fefo-suggestion`, { display_unit });
}

// ── Transactions ────────────────────────────────────────────────
export interface CreateTransactionBody {
  type: TransactionType;
  at?: string | null;
  note?: string | null;
  qty_input?: string | null;
  input_unit?: string | null;
  unit_price?: string | null;
  currency?: string | null;
  ref_sample_id?: string | null;
  confirm_warning?: boolean;
  actual_qty_input?: string | null;
  delta_input?: string | null;
}
export function createTransaction(lotId: string, body: CreateTransactionBody) {
  return apiPost<Transaction>(`/lots/${lotId}/transactions`, body);
}

export interface TransactionFilters {
  chemical_id?: string;
  lot_id?: string;
  ref_sample_id?: string;
  by_user?: string;
  type?: string;
  date_from?: string;
  date_to?: string;
  department_id?: string;
  display_unit?: string;
  page?: number;
  limit?: number;
}
export function listTransactions(f: TransactionFilters = {}) {
  return apiGetPaged<Transaction[]>('/transactions', { ...f });
}

export interface RecheckBody {
  result: 'pass' | 'fail';
  checked_at: string;
  next_recheck_date?: string | null;
  note?: string | null;
}
export function createRecheck(lotId: string, body: RecheckBody) {
  return apiPost(`/lots/${lotId}/rechecks`, body);
}

// ── Inventory ───────────────────────────────────────────────────
export function listLowStock(department_id?: string, page = 1, limit = 50) {
  return apiGetPaged<LowStockItem[]>('/inventory/low-stock', { department_id, page, limit });
}

// ── Export ──────────────────────────────────────────────────────
export async function exportTransactionsXlsx(params: { date_from: string; date_to: string; type?: string }) {
  const { blob, filename } = await apiDownload('/exports/transactions.xlsx', { ...params });
  saveBlob(blob, filename);
}
