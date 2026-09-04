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

// Correlation-id của request gần nhất — ErrorBoundary hiển thị cho người dùng
// đọc cho quản trị viên, để tra đúng dòng log tương ứng.
let _lastCorrelationId: string | null = null;
export function getLastCorrelationId(): string | null {
  return _lastCorrelationId;
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
  /** Header bổ sung (vd Idempotency-Key). */
  headers?: Record<string, string>;
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

// ───────────────────────────── Timeout ─────────────────────────────
//
// Không có timeout, mất mạng giữa chừng làm request treo tới khi trình duyệt tự bỏ
// cuộc (hàng phút). useAsync không bao giờ settle ⇒ trang quay vòng vô hạn và
// ErrorState không bao giờ hiện.
//
// CỐ Ý không dùng AbortSignal.any(): nó mới (Chrome 116+/Safari 17.4+) và ở đây chỉ
// cần ghép đúng 2 tín hiệu — tự nối bằng AbortController chạy được ở mọi trình duyệt
// đã hỗ trợ fetch.
const DEFAULT_TIMEOUT_MS = 30_000;
/** Upload/tải tệp lớn hợp lệ có thể lâu hơn nhiều — không áp cùng ngưỡng với JSON. */
const TRANSFER_TIMEOUT_MS = 120_000;

interface TimedSignal {
  signal: AbortSignal;
  /** Gọi sau khi request settle để dọn timer + listener (tránh rò rỉ). */
  done: () => void;
}

function withTimeout(outer: AbortSignal | undefined, ms: number): TimedSignal {
  const ac = new AbortController();
  const timer = setTimeout(
    () => ac.abort(new DOMException('Hết thời gian chờ máy chủ', 'TimeoutError')),
    ms,
  );
  const onOuterAbort = () => ac.abort(outer?.reason);
  if (outer) {
    if (outer.aborted) ac.abort(outer.reason);
    else outer.addEventListener('abort', onOuterAbort, { once: true });
  }
  return {
    signal: ac.signal,
    done: () => {
      clearTimeout(timer);
      outer?.removeEventListener('abort', onOuterAbort);
    },
  };
}

/** True nếu lỗi là do timeout của ta (khác với huỷ chủ động khi đổi trang). */
export function isTimeoutError(err: unknown): boolean {
  return (err as { name?: string } | null)?.name === 'TimeoutError';
}

// ───────────────────────── Refresh token ─────────────────────────

let refreshPromise: Promise<boolean> | null = null;

const REFRESH_LOCK = 'lims-token-refresh';

/** Gọi thật endpoint refresh. Chỉ được chạy khi đang giữ khoá. */
async function refreshOnce(): Promise<boolean> {
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
  }
}

/**
 * Gọi refresh token; trả true nếu cấp được access token mới.
 *
 * HAI LỚP CHỐNG ĐUA — hai phạm vi khác nhau, cần cả hai:
 *
 * 1. `refreshPromise` — gộp trong MỘT tab. Nhiều request cùng nhận 401 thì chỉ một
 *    lần gọi mạng.
 *
 * 2. Web Locks — gộp GIỮA CÁC TAB. Đây mới là lớp quan trọng: `refreshPromise` là
 *    biến module nên mỗi tab có bản riêng. Với ACCESS_TOKEN_TTL_MINUTES=10 cộng
 *    polling 30s (Topbar) và 60s (badge), hai tab mở song song sẽ chạm 401 gần như
 *    cùng lúc và cùng POST /auth/refresh với CÙNG cookie. Backend khoá hàng bằng
 *    with_for_update nên hai request bị tuần tự hoá: tab thắng xoay token, tab thua
 *    trình ra refresh token vừa bị thu hồi ⇒ auth_service kích hoạt reuse detection
 *    ⇒ THU HỒI TOÀN BỘ phiên của người dùng trên mọi thiết bị.
 *    (Xem docs/frontend/FRONTEND_SECURITY_AUDIT.md FE-S-02.)
 *
 *    Tab vào sau khi có khoá sẽ thấy token trong localStorage ĐÃ KHÁC lúc nó bắt
 *    đầu chờ — nghĩa là tab khác vừa xoay xong — nên dùng luôn token đó thay vì gọi
 *    lại. Đó là lý do phải chụp `tokenBefore` TRƯỚC khi xin khoá.
 */
async function doRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  const tokenBefore = getToken();
  const run = async (): Promise<boolean> => {
    if (getToken() !== tokenBefore) return true; // tab khác đã xoay xong trong lúc chờ
    return refreshOnce();
  };

  refreshPromise = (async () => {
    try {
      const locks = (navigator as Navigator & { locks?: LockManager }).locks;
      if (locks) return await locks.request(REFRESH_LOCK, run);
      return await run(); // trình duyệt không hỗ trợ Web Locks → vẫn chạy, chỉ mất lớp 2
    } finally {
      // reset sau microtask để các request song song cùng dùng 1 lần refresh
      setTimeout(() => (refreshPromise = null), 0);
    }
  })();
  return refreshPromise;
}


/** Callback khi phiên hết hạn hoàn toàn (refresh fail) — AuthContext đăng ký. */
let onSessionExpired: (() => void) | null = null;
export function setOnSessionExpired(cb: (() => void) | null) {
  onSessionExpired = cb;
}

// Tab khác đăng xuất (hoặc mất phiên) → tab này phải theo. Không có cái này, người
// dùng bấm tiếp ở tab còn lại và nhận một chuỗi lỗi 401 khó hiểu.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === TOKEN_KEY && e.newValue === null) onSessionExpired?.();
  });
}

async function rawRequest(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const correlationId = uuid();
  _lastCorrelationId = correlationId;
  const headers: Record<string, string> = {
    'x-correlation-id': correlationId,
    Accept: opts.raw ? '*/*' : 'application/json',
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  Object.assign(headers, opts.headers ?? {});
  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  const t = withTimeout(opts.signal, opts.raw ? TRANSFER_TIMEOUT_MS : DEFAULT_TIMEOUT_MS);
  try {
    return await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? 'GET',
      credentials: 'include',
      headers,
      body,
      signal: t.signal,
    });
  } finally {
    t.done();
  }
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
export async function apiPost<T>(
  path: string,
  body?: unknown,
  query?: RequestOptions['query'],
  /**
   * Idempotency-Key. Backend đã có IdempotencyMiddleware nhưng nó là opt-in và
   * frontend chưa bao giờ gửi header này, nên middleware chưa từng kích hoạt.
   *
   * Sinh tự động ở đây ⇒ lần retry sau 401→refresh dùng LẠI đúng key, không tạo
   * bản ghi trùng. Muốn chặn cả double-click thì component phải tự sinh key và
   * giữ trong ref rồi truyền vào — vì mỗi lần bấm là một lời gọi apiPost mới.
   */
  idempotencyKey?: string,
): Promise<T> {
  const key = idempotencyKey ?? crypto.randomUUID();
  return (
    await request<T>(path, {
      method: 'POST',
      body,
      query,
      headers: { 'Idempotency-Key': key },
    })
  ).data;
}
export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return (await request<T>(path, { method: 'PATCH', body })).data;
}
export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return (await request<T>(path, { method: 'PUT', body })).data;
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

/** POST multipart có timeout dài (tệp lớn) — dùng chung cho 2 hàm upload bên dưới. */
async function postForm(path: string, method: 'POST' | 'PUT', headers: Record<string, string>, form: FormData) {
  const t = withTimeout(undefined, TRANSFER_TIMEOUT_MS);
  try {
    return await fetch(buildUrl(path), { method, credentials: 'include', headers, body: form, signal: t.signal });
  } finally {
    t.done();
  }
}

/** Upload multipart (file đính kèm). */
export async function apiUpload<T>(path: string, file: File, fieldName = 'file'): Promise<T> {
  const form = new FormData();
  form.append(fieldName, file);
  const correlationId = uuid();
  _lastCorrelationId = correlationId;
  const headers: Record<string, string> = { 'x-correlation-id': correlationId };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res = await postForm(path, 'POST', headers, form);
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) {
      res = await postForm(path, 'POST', { ...headers, Authorization: `Bearer ${getToken()}` }, form);
    } else {
      // Trước đây thiếu nhánh này (3 đường gọi kia đều có): refresh hỏng thì người
      // dùng ở lại trạng thái "đã đăng nhập" với token chết, mọi thao tác sau đó lỗi
      // khó hiểu thay vì được đưa về trang đăng nhập.
      setToken(null);
      onSessionExpired?.();
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
  let res = await postForm(path, method, headers, form);
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) {
      res = await postForm(path, method, { ...headers, Authorization: `Bearer ${getToken()}` }, form);
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
