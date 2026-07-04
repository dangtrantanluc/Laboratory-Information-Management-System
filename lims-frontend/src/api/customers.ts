import { apiGet, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type { Customer } from '@/types';

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
  contact?: string | null;
  type?: string;
  note?: string | null;
}
export function createCustomer(body: CustomerBody) {
  return apiPost<Customer>('/customers', body);
}
export function updateCustomer(id: string, body: CustomerBody) {
  return apiPatch<Customer>(`/customers/${id}`, body);
}
