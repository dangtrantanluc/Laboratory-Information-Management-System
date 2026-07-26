import { apiGet, apiPost } from '@/lib/api';

export function getVapidPublicKey() {
  return apiGet<{ public_key: string }>('/push/vapid-public-key');
}

export function subscribePush(body: {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string;
}) {
  return apiPost<Record<string, never>>('/push/subscribe', body);
}

export function unsubscribePush(endpoint: string) {
  return apiPost<Record<string, never>>('/push/unsubscribe', { endpoint });
}
