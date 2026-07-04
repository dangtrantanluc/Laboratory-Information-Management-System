import { apiGet, apiPatch, apiPost, request, setToken } from '@/lib/api';
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
