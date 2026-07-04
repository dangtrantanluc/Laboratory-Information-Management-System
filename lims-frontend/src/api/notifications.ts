import { apiGet, apiGetPaged, apiPatch } from '@/lib/api';
import type { Notification } from '@/types';

export function listNotifications(params: { unread?: boolean; type?: string; page?: number; limit?: number } = {}) {
  return apiGetPaged<Notification[]>('/notifications', { ...params });
}
export function getUnreadCount() {
  return apiGet<{ unread_count: number }>('/notifications/unread-count');
}
export function markRead(id: string) {
  return apiPatch<{ id: string; read_at: string }>(`/notifications/${id}/read`);
}
export function markAllRead() {
  return apiPatch<{ marked_read: number }>('/notifications/read-all');
}
