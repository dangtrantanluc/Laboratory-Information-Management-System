import { useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { Footer } from './Footer';
import { LoadingState } from '@/components/ui/States';
import { usePageViewTracking } from '@/lib/usePageViewTracking';

export function AppShell() {
  const { user, loading, mustChangePassword } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  usePageViewTracking();

  if (loading) {
    return (
      <div className="flex h-screen-dvh items-center justify-center bg-plate">
        <LoadingState label="Đang khởi tạo phiên làm việc…" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (mustChangePassword) return <Navigate to="/change-password" replace />;

  return (
    <div className="flex h-screen-dvh overflow-hidden bg-plate">
      {/* Bỏ qua điều hướng — sidebar có ~50 link, người dùng bàn phím không nên
          phải Tab hết mới tới nội dung. Chỉ hiện khi được focus. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-lg focus:bg-blueberry focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-pop"
      >
        Bỏ qua điều hướng
      </a>

      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onMobileOpen={() => setMobileOpen(true)}
        onMobileClose={() => setMobileOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMobileMenu={() => setMobileOpen(true)} />
        {/* Footer nằm TRONG main để cuộn cùng nội dung — trước đây nó là flex item
            cố định ngoài vùng cuộn, ăn ~110px chiều cao viewport ở mọi trang. */}
        <main id="main-content" className="flex flex-1 flex-col overflow-y-auto scrollbar-thin">
          {/* key theo URL → remount wrapper mỗi lần đổi trang để chạy lại animation vào trang */}
          <div
            key={location.pathname}
            className="mx-auto w-full max-w-[1400px] flex-1 animate-page-in px-3 py-4 sm:px-4 sm:py-6 lg:px-8 3xl:max-w-[1760px]"
          >
            <Outlet />
          </div>
          <Footer />
        </main>
      </div>
    </div>
  );
}
