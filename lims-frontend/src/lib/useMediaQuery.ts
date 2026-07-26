import { useEffect, useState } from 'react';

/**
 * Theo dõi một media query.
 *
 * Ưu tiên dùng class Tailwind (`md:grid-cols-2`) khi chỉ đổi style — không tốn re-render.
 * Chỉ dùng hook này khi cần đổi CẤU TRÚC DOM (bảng ↔ thẻ) hoặc giá trị JS (chiều cao chart).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : false,
  );

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    // Đồng bộ lại phòng khi query đổi giữa các lần render
    setMatches(mql.matches);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** Ngưỡng breakpoint — PHẢI khớp với `theme.extend.screens` trong tailwind.config.js. */
export const BP = {
  xs: 480,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
  '3xl': 1920,
} as const;

export type BreakpointKey = keyof typeof BP;

/** true khi viewport ≥ ngưỡng. `useUp('md')` ⇔ tiền tố Tailwind `md:` */
export function useUp(bp: BreakpointKey): boolean {
  return useMediaQuery(`(min-width: ${BP[bp]}px)`);
}

/** true khi viewport < ngưỡng. `useDown('md')` ⇔ "dưới md" (`max-md:`) */
export function useDown(bp: BreakpointKey): boolean {
  return useMediaQuery(`(max-width: ${BP[bp] - 0.02}px)`);
}

/** Thiết bị cảm ứng (không có con trỏ chính xác). */
export function useCoarsePointer(): boolean {
  return useMediaQuery('(pointer: coarse)');
}

/** Người dùng bật "giảm chuyển động" ở hệ điều hành. */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}
