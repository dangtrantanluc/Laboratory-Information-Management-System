import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPageView } from '@/api/reporting';

/**
 * Ghi 1 lượt "xem trang chính" mỗi khi điều hướng client-side (SPA) — bổ sung middleware HTTP (M6 #14).
 * Best-effort: lỗi bỏ qua, không chặn UI. Chỉ gửi pathname (không query nhạy cảm).
 * Backend tự lọc theo whitelist trang chính (path ngoài whitelist bị bỏ qua âm thầm).
 */
export function usePageViewTracking() {
  const location = useLocation();
  const last = useRef<string>('');

  useEffect(() => {
    const path = location.pathname;
    if (path === last.current) return;
    last.current = path;
    void trackPageView(path);
  }, [location.pathname]);
}
