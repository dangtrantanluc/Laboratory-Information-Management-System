import { apiGetPaged } from '@/lib/api';
import type { AuditLog } from '@/types';

export interface AuditFilters {
  user_id?: string;
  action?: string;
  resource?: string;
  resource_id?: string;
  correlation_id?: string;
  date_from?: string;
  date_to?: string;
  ip?: string;
  page?: number;
  limit?: number;
}
export function listAuditLogs(f: AuditFilters = {}) {
  return apiGetPaged<AuditLog[]>('/audit-logs', { ...f });
}
