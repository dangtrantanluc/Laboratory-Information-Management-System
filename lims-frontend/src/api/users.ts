import { apiDelete, apiGet, apiGetPaged, apiPatch, apiPost } from '@/lib/api';
import type { Department, Role, RoleMeta, UserListItem } from '@/types';

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

/* ═══════════════ m30: duyệt tài khoản tự đăng ký (chỉ admin) ═══════════════ */

export interface ApproveUserBody {
  role: Role;
  department_id?: string | null;
  is_dept_lead?: boolean;
}

/** Duyệt tài khoản đang chờ: gán vai trò + phòng ban thật rồi kích hoạt. */
export async function approveUser(id: string, body: ApproveUserBody): Promise<void> {
  await apiPost(`/users/${id}/approve`, body);
}

/** Từ chối yêu cầu mở tài khoản (chuyển 'disabled', gửi mail báo lý do). */
export async function rejectUser(id: string, reason: string): Promise<void> {
  await apiPost(`/users/${id}/reject`, { reason });
}

/* ═══════════ m49: tài khoản bị khoá đăng nhập (chỉ admin) ═══════════ */

export interface LockoutEntry {
  email: string;
  /** Khoá đặt theo cặp (email, IP) — một người có thể bị khoá ở nhiều IP. */
  ip: string;
  remaining_seconds: number;
  failed_attempts?: number | null;
  user_id?: string | null;
  full_name?: string | null;
  /** false = email không ứng với tài khoản nào → dấu hiệu có người dò email. */
  is_known_account: boolean;
}

export interface LockoutSnapshot {
  locked: LockoutEntry[];
  failing: LockoutEntry[];
}

/** Ảnh chụp hiện tại. Khoá nằm ở Redis và tự hết hạn — lịch sử xem ở Nhật ký hệ thống. */
export function listLockouts() {
  return apiGet<LockoutSnapshot>('/users/lockouts');
}

/** Mở khoá ngay, xoá khoá ở MỌI IP của tài khoản đó kèm bộ đếm sai. */
export async function unlockUser(id: string): Promise<void> {
  await apiPost(`/users/${id}/unlock`, {});
}
