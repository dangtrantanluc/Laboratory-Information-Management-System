import { apiDelete, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type { Department, RoleMeta, UserListItem } from '@/types';

export interface UserFilters {
  q?: string;
  role?: string;
  department_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export function listUsers(f: UserFilters = {}) {
  return apiGetPaged<UserListItem[]>('/users', { ...f });
}

export interface CreateUserBody {
  email: string;
  full_name: string;
  role: string;
  department_id?: string | null;
  password?: string | null;
  is_dept_lead?: boolean;
}
export function createUser(body: CreateUserBody) {
  return apiPost<UserListItem>('/users', body);
}

export interface UpdateUserBody {
  full_name?: string;
  role?: string;
  department_id?: string | null;
  email?: string;
}
export function updateUser(id: string, body: UpdateUserBody) {
  return apiPatch<UserListItem>(`/users/${id}`, body);
}

export function enableUser(id: string) {
  return apiPost(`/users/${id}/enable`);
}
export function disableUser(id: string) {
  return apiPost(`/users/${id}/disable`);
}
export function resetPassword(id: string, new_password?: string) {
  return apiPost<{ id: string; must_change_password: boolean }>(`/users/${id}/reset-password`, {
    new_password: new_password ?? null,
  });
}

export function listRoles() {
  return apiGetPaged<RoleMeta[]>('/roles');
}

// ── Departments ─────────────────────────────────────────────────
export function listDepartments(include_inactive = false) {
  return apiGetPaged<Department[]>('/departments', { include_inactive });
}
export interface DepartmentBody {
  name?: string;
  code?: string;
  parent_id?: string | null;
  lead_user_id?: string | null;
}
export function createDepartment(body: DepartmentBody) {
  return apiPost<Department>('/departments', body);
}
export function updateDepartment(id: string, body: DepartmentBody) {
  return apiPatch<Department>(`/departments/${id}`, body);
}
export function deleteDepartment(id: string) {
  return apiDelete(`/departments/${id}`);
}
