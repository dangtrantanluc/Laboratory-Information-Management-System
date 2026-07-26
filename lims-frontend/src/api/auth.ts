import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, request, setToken } from '@/lib/api';
import type { CurrentUser, LoginResponse } from '@/types';

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await apiPost<LoginResponse>('/auth/login', { email, password });
  if (data.access_token) setToken(data.access_token);
  return data;
}

export async function getMe(): Promise<CurrentUser> {
  return apiGet<CurrentUser>('/auth/me');
}

export interface UpdateMeBody {
  full_name?: string;
  email?: string;
}

/** Tự cập nhật hồ sơ cá nhân (chỉ họ tên/email). */
export async function updateMe(body: UpdateMeBody): Promise<void> {
  await apiPatch('/auth/me', body);
}

export async function changePassword(current_password: string, new_password: string): Promise<void> {
  await apiPatch('/auth/me/password', { current_password, new_password });
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST', body: {}, skipRefresh: true });
  } catch {
    /* ignore */
  }
  setToken(null);
}

/* ═══════════════════ m30: tự đăng ký, quên mật khẩu, phiên, avatar ═══════════════════ */

export interface RegistrationConfig {
  enabled: boolean;
  allowed_domains: string[];
}

/** Hỏi trước khi hiện form: hệ thống có mở đăng ký không, giới hạn tên miền nào. */
export async function getRegistrationConfig(): Promise<RegistrationConfig> {
  return apiGet<RegistrationConfig>('/auth/registration-config');
}

/** Đăng ký. Backend LUÔN trả cùng thông điệp dù email đã tồn tại hay chưa. */
export async function register(body: {
  email: string;
  full_name: string;
  password: string;
}): Promise<{ message: string }> {
  return apiPost<{ message: string }>('/auth/register', body);
}

export interface VerifyEmailResult {
  email: string;
  already_verified: boolean;
  status: string;
  awaiting_approval: boolean;
}

export async function verifyEmail(token: string): Promise<VerifyEmailResult> {
  return apiPost<VerifyEmailResult>('/auth/verify-email', { token });
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return apiPost<{ message: string }>('/auth/forgot-password', { email });
}

export async function resetPassword(token: string, new_password: string): Promise<{ message: string }> {
  return apiPost<{ message: string }>('/auth/reset-password', { token, new_password });
}

export interface LoginSession {
  id: string;
  device: string;
  is_mobile: boolean;
  ip: string | null;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export async function listSessions(): Promise<LoginSession[]> {
  return apiGet<LoginSession[]>('/auth/me/sessions');
}

export async function revokeSession(id: string): Promise<void> {
  await apiDelete(`/auth/me/sessions/${id}`);
}

export async function revokeOtherSessions(): Promise<{ revoked_count: number }> {
  return apiPost<{ revoked_count: number }>('/auth/me/sessions/revoke-others');
}

export async function uploadAvatar(file: File): Promise<{ avatar_url: string }> {
  return apiUpload<{ avatar_url: string }>('/auth/me/avatar', file);
}

export async function removeAvatar(): Promise<void> {
  await apiDelete('/auth/me/avatar');
}
