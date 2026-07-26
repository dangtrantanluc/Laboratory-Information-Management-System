/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // Thang breakpoint: giữ nguyên mặc định Tailwind, thêm 2 mốc ở hai đầu.
      // xs  — phone lớn (KPI 2 cột sớm hơn)
      // 3xl — màn 2K trở lên (nới max-width, thêm cột)
      // Ngưỡng phải khớp với BP trong src/lib/useMediaQuery.ts.
      screens: {
        xs: '480px',
        '3xl': '1920px',
      },
      colors: {
        // Token màu dùng CSS variable (R G B) — định nghĩa tại :root trong index.css.
        // Hỗ trợ opacity modifier (vd bg-blueberry/40) qua cú pháp rgb(var() / <alpha-value>).
        blueberry: 'rgb(var(--c-blueberry) / <alpha-value>)', // primary
        berry: 'rgb(var(--c-berry) / <alpha-value>)', // accent (info/badge)
        stem: 'rgb(var(--c-stem) / <alpha-value>)', // text/icon phụ
        yogurt: 'rgb(var(--c-yogurt) / <alpha-value>)',
        plate: 'rgb(var(--c-plate) / <alpha-value>)', // app background
        surface: 'rgb(var(--c-surface) / <alpha-value>)', // mặt thẻ/card/sidebar (thay bg-white)
        surface2: 'rgb(var(--c-surface2) / <alpha-value>)', // mặt nâng nhẹ (hover/input)
        // Semantic
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        subink: 'rgb(var(--c-subink) / <alpha-value>)',
        hairline: 'rgb(var(--c-hairline) / <alpha-value>)',
        // Status
        success: 'rgb(var(--c-success) / <alpha-value>)',
        pending: 'rgb(var(--c-pending) / <alpha-value>)',
        warning: 'rgb(var(--c-warning) / <alpha-value>)',
        overdue: 'rgb(var(--c-overdue) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        xl: '12px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)',
        pop: '0 8px 24px rgba(16, 24, 40, 0.12)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'translateY(8px) scale(0.98)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'slide-in': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        // Chuyển trang: nội dung mờ dần + trượt nhẹ lên
        'page-in': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        // Nhịp thở nhẹ cho badge/chấm cảnh báo (dịu hơn animate-pulse mặc định)
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
        // "Nảy mầm": mọc lên từ dưới + giãn nhẹ (vibe sinh trưởng của viện sinh học)
        sprout: {
          '0%': { opacity: '0', transform: 'translateY(10px) scale(0.94)' },
          '60%': { opacity: '1', transform: 'translateY(-2px) scale(1.01)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        // Lá đảo nhẹ như gió thoảng — dùng cho hoạ tiết trang trí
        sway: {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        // Bottom-sheet trên mobile: trượt lên từ đáy màn hình
        'slide-up': {
          from: { transform: 'translateY(100%)' },
          to: { transform: 'translateY(0)' },
        },
        // Popup neo từ trên xuống (dropdown thông báo dạng sheet)
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.15s ease-out',
        'scale-in': 'scale-in 0.16s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in': 'slide-in 0.2s ease-out',
        'page-in': 'page-in 0.26s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        sprout: 'sprout 0.42s cubic-bezier(0.16, 1, 0.3, 1) both',
        sway: 'sway 7s ease-in-out infinite',
        'slide-up': 'slide-up 0.24s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slide-down 0.18s ease-out',
      },
    },
  },
  plugins: [],
};
