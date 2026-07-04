/**
 * API client — wrapper fetch duy nhất cho toàn FE.
 * - Base URL từ env (không hardcode).
 * - Gắn Authorization: Bearer <token> + x-correlation-id mỗi request.
 * - Gửi cookie (credentials: include) cho refresh token HttpOnly.
 * - Unwrap { success, data, meta }; lỗi → throw ApiError(code, message, status, details, correlationId).
 * - Tự refresh access token khi 401 rồi retry 1 lần.
 * Không gọi fetch trực tiếp trong component.
 */
import type { PageMeta } from '@/types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8060/api/v1';

const TOKEN_KEY = 'lims_access_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;
  correlationId?: string;
  constructor(opts: {
    code: string;
    message: string;
    status: number;
    details?: unknown;
    correlationId?: string;
  }) {
    super(opts.message);
    this.name = 'ApiError';
    this.code = opts.code;
    this.status = opts.status;
    this.details = opts.details;
    this.correlationId = opts.correlationId;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Bỏ qua auto-refresh (dùng cho chính endpoint refresh/login). */
  skipRefresh?: boolean;
  /** Nhận blob (file PDF / Excel) thay vì JSON. */
  raw?: boolean;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  // Hỗ trợ cả base tuyệt đối (http://host/api/v1) lẫn base tương đối (/api/v1 — same-origin qua nginx proxy)
  const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
  const url = new URL(API_BASE_URL + path, base);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

let refreshPromise: Promise<boolean> | null = null;

/** Gọi refresh token; trả true nếu cấp được access token mới. */
async function doRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(API_BASE_URL + '/auth/refresh', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'x-correlation-id': uuid() },
          body: JSON.stringify({}),
        });
        if (!res.ok) return false;
        const json = await res.json();
        if (json?.success && json?.data?.access_token) {
          setToken(json.data.access_token);
          return true;
        }
        return false;
      } catch {
        return false;
      } finally {
        // reset sau microtask để các request song song cùng dùng 1 lần refresh
        setTimeout(() => (refreshPromise = null), 0);
      }
    })();
  }
  return refreshPromise;
}

/** Callback khi phiên hết hạn hoàn toàn (refresh fail) — AuthContext đăng ký. */
let onSessionExpired: (() => void) | null = null;
export function setOnSessionExpired(cb: (() => void) | null) {
  onSessionExpired = cb;
}

async function rawRequest(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const correlationId = uuid();
  const headers: Record<string, string> = {
    'x-correlation-id': correlationId,
    Accept: opts.raw ? '*/*' : 'application/json',
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  return fetch(buildUrl(path, opts.query), {
    method: opts.method ?? 'GET',
    credentials: 'include',
    headers,
    body,
    signal: opts.signal,
  });
}

async function parseError(res: Response): Promise<ApiError> {
  let code = 'HTTP_ERROR';
  let message = 'Lỗi kết nối, vui lòng thử lại';
  let details: unknown;
  let correlationId: string | undefined = res.headers.get('x-correlation-id') ?? undefined;
  try {
    const json = await res.json();
    if (json?.error) {
      code = json.error.code ?? code;
      message = json.error.message ?? message;
      details = json.error.details;
      correlationId = json.error.correlationId ?? correlationId;
    }
  } catch {
    /* non-JSON */
  }
  return new ApiError({ code, message, status: res.status, details, correlationId });
}

interface ApiResult<T> {
  data: T;
  meta?: PageMeta;
}

/** Request trả JSON unwrap { data, meta }. */
export async function request<T>(path: string, opts: RequestOptions = {}): Promise<ApiResult<T>> {
  let res = await rawRequest(path, opts, getToken());

  if (res.status === 401 && !opts.skipRefresh) {
    const ok = await doRefresh();
    if (ok) {
      res = await rawRequest(path, opts, getToken());
    } else {
      setToken(null);
      onSessionExpired?.();
    }
  }

  if (res.status === 204) return { data: undefined as T };

  if (!res.ok) throw await parseError(res);

  const json = await res.json();
  if (json && json.success === false) throw await parseError(res);
  return { data: json.data as T, meta: json.meta as PageMeta | undefined };
}

/** Helper trả thẳng data. */
export async function apiGet<T>(path: string, query?: RequestOptions['query']): Promise<T> {
  return (await request<T>(path, { method: 'GET', query })).data;
}
export async function apiGetPaged<T>(
  path: string,
  query?: RequestOptions['query'],
): Promise<ApiResult<T>> {
  return request<T>(path, { method: 'GET', query });
}
export async function apiPost<T>(path: string, body?: unknown, query?: RequestOptions['query']): Promise<T> {
  return (await request<T>(path, { method: 'POST', body, query })).data;
}
export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return (await request<T>(path, { method: 'PATCH', body })).data;
}
export async function apiDelete(path: string): Promise<void> {
  await request<void>(path, { method: 'DELETE' });
}

/** Tải file binary (PDF / Excel) — trả blob + filename gợi ý. */
export async function apiDownload(
  path: string,
  query?: RequestOptions['query'],
): Promise<{ blob: Blob; filename: string }> {
  let res = await rawRequest(path, { method: 'GET', query, raw: true }, getToken());
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) res = await rawRequest(path, { method: 'GET', query, raw: true }, getToken());
    else {
      setToken(null);
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition') ?? '';
  const m = /filename="?([^"]+)"?/.exec(cd);
  return { blob, filename: m?.[1] ?? 'download' };
}

/** Upload multipart (file đính kèm). */
export async function apiUpload<T>(path: string, file: File, fieldName = 'file'): Promise<T> {
  const form = new FormData();
  form.append(fieldName, file);
  const correlationId = uuid();
  const headers: Record<string, string> = { 'x-correlation-id': correlationId };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res = await fetch(buildUrl(path), { method: 'POST', credentials: 'include', headers, body: form });
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) {
      const h2 = { ...headers, Authorization: `Bearer ${getToken()}` };
      res = await fetch(buildUrl(path), { method: 'POST', credentials: 'include', headers: h2, body: form });
    }
  }
  if (!res.ok) throw await parseError(res);
  const json = await res.json();
  return json.data as T;
}

/**
 * Upload multipart kèm nhiều field (file + các field text).
 * Dùng cho tạo tài liệu / tạo version M3 (file + title/type/change_note...).
 * Bỏ qua field undefined/null; File append nguyên vẹn.
 */
export async function apiUploadForm<T>(
  path: string,
  fields: Record<string, string | number | boolean | File | undefined | null>,
  opts: { method?: 'POST' | 'PUT' } = {},
): Promise<T> {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    if (v === undefined || v === null) continue;
    if (v instanceof File) form.append(k, v);
    else form.append(k, String(v));
  }
  const method = opts.method ?? 'POST';
  const headers: Record<string, string> = { 'x-correlation-id': uuid() };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res = await fetch(buildUrl(path), { method, credentials: 'include', headers, body: form });
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) {
      const h2 = { ...headers, Authorization: `Bearer ${getToken()}` };
      res = await fetch(buildUrl(path), { method, credentials: 'include', headers: h2, body: form });
    } else {
      setToken(null);
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await parseError(res);
  const json = await res.json();
  if (json && json.success === false) throw await parseError(res);
  return json.data as T;
}

/** Trigger tải blob về máy. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
