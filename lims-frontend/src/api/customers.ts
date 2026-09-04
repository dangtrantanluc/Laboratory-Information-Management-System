import { apiDelete, apiGet, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type { Customer, CustomerContact } from '@/types';

export interface CustomerFilters {
  q?: string;
  type?: string;
  page?: number;
  limit?: number;
}
export function listCustomers(f: CustomerFilters = {}) {
  return apiGetPaged<Customer[]>('/customers', { ...f });
}
export function getCustomer(id: string) {
  return apiGet<Customer>(`/customers/${id}`);
}
export interface CustomerBody {
  name?: string;
  type?: string;
  note?: string | null;
  address?: string | null;
  tax_code?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
}
export function createCustomer(body: CustomerBody) {
  return apiPost<Customer>('/customers', body);
}
export function updateCustomer(id: string, body: CustomerBody) {
  return apiPatch<Customer>(`/customers/${id}`, body);
}


// ── m35: danh bạ liên hệ ─────────────────────────────────────────
export interface CustomerContactBody {
  full_name?: string;
  job_title?: string | null;
  email?: string | null;
  phone?: string | null;
  is_primary?: boolean;
  is_active?: boolean;
  note?: string | null;
}

/**
 * @param includeInactive false = chỉ người còn hiệu lực. Quầy nhận mẫu PHẢI truyền
 * false: không được chọn người đã nghỉ việc vào phiếu mới.
 */
export function listCustomerContacts(customerId: string, includeInactive = true) {
  return apiGet<CustomerContact[]>(
    `/customers/${customerId}/contacts?include_inactive=${includeInactive}`,
  );
}
export function createCustomerContact(customerId: string, body: CustomerContactBody) {
  return apiPost<CustomerContact>(`/customers/${customerId}/contacts`, body);
}
export function updateCustomerContact(
  customerId: string, contactId: string, body: CustomerContactBody,
) {
  return apiPatch<CustomerContact>(`/customers/${customerId}/contacts/${contactId}`, body);
}
/** Xoá hẳn dòng nhập nhầm. Người nghỉ việc: dùng updateCustomerContact({is_active:false}). */
export function deleteCustomerContact(customerId: string, contactId: string) {
  return apiDelete(`/customers/${customerId}/contacts/${contactId}`);
}
