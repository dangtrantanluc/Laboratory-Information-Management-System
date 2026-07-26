import { useEffect, type RefObject } from 'react';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function focusableIn(root: HTMLElement): HTMLElement[] {
  // offsetParent === null ⇒ phần tử đang ẩn (display:none hoặc cha bị ẩn)
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
}

/**
 * Giam focus bên trong `ref` khi `active`. Khi tắt, trả focus về phần tử đã mở overlay.
 * Dùng cho Modal, ConfirmDialog, drawer sidebar, sheet bộ lọc.
 */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const root = ref.current;
    if (!root) return;

    const prevActive = document.activeElement as HTMLElement | null;

    // Focus phần tử đầu tiên bên trong; nếu không có thì focus chính container.
    const first = focusableIn(root)[0];
    if (first) {
      first.focus();
    } else {
      root.setAttribute('tabindex', '-1');
      root.focus();
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab' || !root) return;
      const items = focusableIn(root);
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      const current = document.activeElement;

      // Focus đã lọt ra ngoài (vd click chỗ khác) → kéo về đầu
      if (!root.contains(current)) {
        e.preventDefault();
        firstEl.focus();
        return;
      }
      if (e.shiftKey && current === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && current === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      // Chỉ trả focus nếu phần tử cũ còn trong DOM
      if (prevActive && document.contains(prevActive)) prevActive.focus?.();
    };
  }, [ref, active]);
}

/**
 * Khoá cuộn `body` khi overlay mở.
 *
 * Dùng bộ đếm tham chiếu vì overlay có thể LỒNG NHAU (ConfirmDialog mở bên trong
 * một Modal). Nếu mỗi overlay tự set/reset `body.style.overflow` thì lớp con đóng
 * lại sẽ mở khoá cuộn dù lớp cha vẫn đang mở — đó là bug của Modal.tsx bản cũ.
 */
let lockCount = 0;
let prevOverflow = '';
let prevPaddingRight = '';

export function useBodyScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;

    if (lockCount === 0) {
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      prevOverflow = document.body.style.overflow;
      prevPaddingRight = document.body.style.paddingRight;
      document.body.style.overflow = 'hidden';
      // Bù đúng bề rộng thanh cuộn để layout không giật khi mở overlay
      if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`;
    }
    lockCount++;

    return () => {
      lockCount--;
      if (lockCount === 0) {
        document.body.style.overflow = prevOverflow;
        document.body.style.paddingRight = prevPaddingRight;
      }
    };
  }, [active]);
}
