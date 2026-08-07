import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, LogOut, Menu, Leaf, ChevronDown, Settings, UserCircle, CheckCheck } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/cn';
import { useDown } from '@/lib/useMediaQuery';
import { ROLE_LABELS, type Notification } from '@/types';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/States';
import { timeAgo } from '@/lib/format';
import { notifTarget } from '@/lib/notifRoute';
import * as notifApi from '@/api/notifications';

export function Topbar({ onMobileMenu }: { onMobileMenu: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="shrink-0">

      {/* Banner chính — logo RIBE + tên trường/viện + tác vụ người dùng.
          Dưới sm: hạ chiều cao 72→56px và bỏ dòng tên trường (bị truncate mất nghĩa
          trên màn 360px), chỉ giữ tên viện dạng rút gọn. */}
      <div className="flex h-14 items-center gap-2 bg-gradient-to-r from-blueberry to-berry px-3 text-white shadow-md sm:h-[72px] sm:gap-3 sm:px-4 lg:px-6">
        {/* Hamburger: chỉ dưới md — từ md trở lên đã có rail sidebar */}
        <button
          onClick={onMobileMenu}
          className="rounded-lg p-2 text-white/80 transition-colors hover:bg-white/15 hover:text-white md:hidden"
          aria-label="Mở menu"
        >
          <Menu size={20} />
        </button>

        <img
          src="/nlu-logo.png"
          alt="Logo Trường Đại học Nông Lâm TP. Hồ Chí Minh"
          className="h-9 w-9 shrink-0 rounded-full bg-white object-contain p-0.5 ring-2 ring-white/70 sm:h-12 sm:w-12"
        />

        <div className="min-w-0 leading-tight">
          <p className="hidden truncate text-[13px] font-bold uppercase tracking-wide text-white sm:block sm:text-[15px]">
            Trường Đại học Nông Lâm TP. Hồ Chí Minh
          </p>
          <p className="truncate text-[12px] font-bold uppercase tracking-wide text-yogurt sm:text-[13px]">
            <span className="sm:hidden">Viện CNSH &amp; Môi trường</span>
            <span className="hidden sm:inline">
              Viện Nghiên cứu Công nghệ Sinh học và Môi trường
            </span>
          </p>
          {user?.department && (
            <span className="mt-0.5 hidden rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold text-white sm:inline-block">
              {user.department.name}
            </span>
          )}
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <NotificationBell />
          <UserMenu
            avatarUrl={user?.avatar_url ?? null}
            name={user?.full_name ?? 'Khách'}
            email={user?.email ?? ''}
            roleLabel={user ? ROLE_LABELS[user.role] : ''}
            onProfile={() => navigate('/profile')}
            onSettings={() => navigate('/settings')}
            onLogout={async () => {
              await logout();
              navigate('/login');
            }}
          />
        </div>
      </div>
    </header>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const isMobile = useDown('sm');

  async function refreshCount() {
    try {
      const c = await notifApi.getUnreadCount();
      setCount(c.unread_count);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const c = await notifApi.getUnreadCount();
        if (active) setCount(c.unread_count);
      } catch {
        /* ignore */
      }
    };
    // Chỉ đếm khi tab đang hiện — xem chú thích cùng lý do ở lib/useNavBadges.ts.
    const tickIfVisible = () => {
      if (document.visibilityState === 'visible') void tick();
    };
    tickIfVisible();
    const t = window.setInterval(tickIfVisible, 30000);
    document.addEventListener('visibilitychange', tickIfVisible);
    return () => {
      active = false;
      window.clearInterval(t);
      document.removeEventListener('visibilitychange', tickIfVisible);
    };
  }, []);

  useEffect(() => {
    const h = (e: MouseEvent) =>
      ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', h);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', h);
      document.removeEventListener('keydown', esc);
    };
  }, []);

  async function loadList() {
    setLoading(true);
    try {
      const res = await notifApi.listNotifications({ limit: 15 });
      setItems(res.data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) await loadList();
  }

  async function onItem(n: Notification) {
    try {
      if (!n.read_at) await notifApi.markRead(n.id);
    } catch {
      /* ignore */
    }
    const target = notifTarget(n);
    if (target) {
      setOpen(false);
      navigate(target);
    } else {
      await loadList();
      refreshCount();
    }
  }

  /** Toggle 2 chiều đã đọc ↔ chưa đọc ngay trong popup. */
  async function toggleRead(n: Notification) {
    try {
      if (n.read_at) await notifApi.markUnread(n.id);
      else await notifApi.markRead(n.id);
      await loadList();
      refreshCount();
    } catch {
      /* ignore */
    }
  }

  async function markAll() {
    try {
      await notifApi.markAllRead();
      await loadList();
      refreshCount();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        className="group relative rounded-lg p-2 text-white/80 transition-all duration-150 hover:bg-white/15 hover:text-white active:scale-90"
        aria-label="Thông báo"
      >
        <Bell size={19} className="transition-transform duration-200 group-hover:-rotate-12" />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 animate-pulse-soft items-center justify-center rounded-full bg-overdue px-1 text-[10px] font-bold text-white ring-2 ring-white/40">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && (
        // Dưới sm: neo full-width dưới topbar thay vì popup 384px bị tràn/cắt mép.
        <div
          className={cn(
            'z-50 rounded-xl border border-hairline bg-surface shadow-pop',
            isMobile
              ? 'fixed inset-x-2 top-[3.5rem] animate-slide-down overflow-hidden'
              : 'absolute right-0 mt-2 w-96 max-w-[calc(100vw-2rem)] animate-scale-in',
          )}
        >
          <div className="flex items-center justify-between gap-2 border-b border-hairline px-4 py-3">
            <p className="text-sm font-semibold text-ink">Thông báo</p>
            {count > 0 && (
              <button onClick={markAll} className="flex items-center gap-1 text-xs text-blueberry hover:underline">
                <CheckCheck size={13} /> Đánh dấu đã đọc hết
              </button>
            )}
          </div>
          <div
            className={cn(
              'overflow-y-auto p-1.5 scrollbar-thin',
              isMobile ? 'max-h-[calc(75dvh-3.5rem)]' : 'max-h-[26rem]',
            )}
          >
            {loading ? (
              <div className="flex justify-center py-6">
                <Spinner className="h-5 w-5" />
              </div>
            ) : items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-subink">Chưa có thông báo</p>
            ) : (
              items.map((n) => (
                <div
                  key={n.id}
                  onClick={() => onItem(n)}
                  className="group flex cursor-pointer items-start gap-2 rounded-lg px-2.5 py-2 transition-colors duration-150 hover:bg-blueberry/8"
                >
                  <span
                    className={
                      'mt-1.5 h-2 w-2 shrink-0 rounded-full ' + (n.read_at ? 'bg-hairline' : 'bg-blueberry')
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <p className={n.read_at ? 'text-sm font-medium text-subink' : 'text-sm font-semibold text-ink'}>
                      {n.title}
                    </p>
                    <p className="line-clamp-2 text-xs text-subink">{n.body}</p>
                    <p className="mt-0.5 text-[11px] text-stem">{timeAgo(n.created_at)}</p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleRead(n);
                    }}
                    aria-label={
                      n.read_at ? `Đánh dấu chưa đọc: ${n.title}` : `Đánh dấu đã đọc: ${n.title}`
                    }
                    className="touch-visible shrink-0 self-center rounded px-2 py-1 text-[10px] text-stem opacity-0 transition hover:bg-hairline/40 hover:text-ink group-hover:opacity-100"
                  >
                    {n.read_at ? 'Chưa đọc' : 'Đã đọc'}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function UserMenu({
  name,
  avatarUrl,
  email,
  roleLabel,
  onProfile,
  onSettings,
  onLogout,
}: {
  name: string;
  avatarUrl?: string | null;
  email: string;
  roleLabel: string;
  onProfile: () => void;
  onSettings: () => void;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) =>
      ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', h);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', h);
      document.removeEventListener('keydown', esc);
    };
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg p-1 pr-2 ring-1 ring-transparent transition-all duration-150 hover:bg-white/15 hover:ring-white/30"
      >
        <Avatar name={name} src={avatarUrl} size="sm" />
        {/* Từ xl mới đủ chỗ cho tên + vai trò. Dưới xl chỉ avatar — bấm vào là
            thấy đầy đủ danh tính trong dropdown. */}
        <div className="hidden text-left xl:block">
          <p className="text-xs font-semibold leading-tight text-white">{name}</p>
          <p className="text-[10px] leading-tight text-white/70">{roleLabel}</p>
        </div>
        <ChevronDown
          size={14}
          className={cn('hidden text-white/80 transition-transform duration-200 xl:block', open && 'rotate-180')}
        />
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-60 animate-scale-in rounded-xl border border-hairline bg-surface p-1.5 shadow-pop">
          <div className="flex items-center gap-3 border-b border-hairline px-2.5 pb-3 pt-1.5">
            <Avatar name={name} src={avatarUrl} size="md" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{name}</p>
              <p className="truncate text-xs text-subink">{email}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-2.5 py-2 text-xs text-subink">
            <Leaf size={14} /> Vai trò: <span className="font-medium text-ink">{roleLabel}</span>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onProfile();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-stem transition-all duration-150 hover:translate-x-0.5 hover:bg-blueberry/10 hover:text-blueberry"
          >
            <UserCircle size={16} /> Hồ sơ cá nhân
          </button>
          <button
            onClick={() => {
              setOpen(false);
              onSettings();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-stem transition-all duration-150 hover:translate-x-0.5 hover:bg-blueberry/10 hover:text-blueberry"
          >
            <Settings size={16} /> Cài đặt & Tài khoản
          </button>
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-overdue transition-all duration-150 hover:translate-x-0.5 hover:bg-overdue/10"
          >
            <LogOut size={16} /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}
