import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, LogOut, Menu, FlaskConical, ChevronDown, Settings, UserCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { ROLE_LABELS, type Notification } from '@/types';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/States';
import { timeAgo } from '@/lib/format';
import * as notifApi from '@/api/notifications';

export function Topbar({ onMobileMenu }: { onMobileMenu: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-hairline bg-white/90 px-4 backdrop-blur lg:px-6">
      <button
        onClick={onMobileMenu}
        className="rounded-lg p-2 text-stem hover:bg-plate lg:hidden"
        aria-label="Mở menu"
      >
        <Menu size={20} />
      </button>

      <div className="hidden items-center gap-2 md:flex">
        <span className="text-sm font-semibold text-ink">Hệ thống Quản lý Phòng Thí nghiệm</span>
        {user?.department && (
          <span className="rounded-md bg-yogurt/20 px-1.5 py-0.5 text-[10px] font-semibold text-[#7a7434]">
            {user.department.name}
          </span>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <NotificationBell />
        <UserMenu
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

  useEffect(() => {
    let active = true;
    const fetchCount = async () => {
      try {
        const c = await notifApi.getUnreadCount();
        if (active) setCount(c.unread_count);
      } catch {
        /* ignore */
      }
    };
    fetchCount();
    const t = window.setInterval(fetchCount, 30000);
    return () => {
      active = false;
      window.clearInterval(t);
    };
  }, []);

  useEffect(() => {
    const h = (e: MouseEvent) =>
      ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      try {
        const res = await notifApi.listNotifications({ limit: 8 });
        setItems(res.data);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    }
  }

  async function onItem(n: Notification) {
    try {
      if (!n.read_at) {
        await notifApi.markRead(n.id);
        setCount((c) => Math.max(0, c - 1));
      }
    } catch {
      /* ignore */
    }
    setOpen(false);
    if (n.ref_type === 'sample' && n.ref_id) navigate(`/samples/sample/${n.ref_id}`);
    else navigate('/notifications');
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        className="relative rounded-lg p-2 text-stem hover:bg-plate hover:text-ink"
        aria-label="Thông báo"
      >
        <Bell size={19} />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-overdue px-1 text-[10px] font-bold text-white">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 animate-scale-in rounded-xl border border-hairline bg-white shadow-pop">
          <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
            <p className="text-sm font-semibold text-ink">Thông báo</p>
            <button
              className="text-xs text-blueberry hover:underline"
              onClick={() => {
                setOpen(false);
                navigate('/notifications');
              }}
            >
              Xem tất cả
            </button>
          </div>
          <div className="max-h-80 overflow-y-auto p-1.5 scrollbar-thin">
            {loading ? (
              <div className="flex justify-center py-6">
                <Spinner className="h-5 w-5" />
              </div>
            ) : items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-subink">Chưa có thông báo</p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => onItem(n)}
                  className="block w-full rounded-lg px-2.5 py-2 text-left hover:bg-plate"
                >
                  <div className="flex items-start gap-2">
                    {!n.read_at && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blueberry" />}
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">{n.title}</p>
                      <p className="line-clamp-2 text-xs text-subink">{n.body}</p>
                      <p className="mt-0.5 text-[11px] text-stem">{timeAgo(n.created_at)}</p>
                    </div>
                  </div>
                </button>
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
  email,
  roleLabel,
  onProfile,
  onSettings,
  onLogout,
}: {
  name: string;
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
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg p-1 pr-2 hover:bg-plate"
      >
        <Avatar name={name} size="sm" />
        <div className="hidden text-left lg:block">
          <p className="text-xs font-semibold leading-tight text-ink">{name}</p>
          <p className="text-[10px] leading-tight text-subink">{roleLabel}</p>
        </div>
        <ChevronDown size={14} className="hidden text-stem lg:block" />
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-60 animate-scale-in rounded-xl border border-hairline bg-white p-1.5 shadow-pop">
          <div className="flex items-center gap-3 border-b border-hairline px-2.5 pb-3 pt-1.5">
            <Avatar name={name} size="md" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{name}</p>
              <p className="truncate text-xs text-subink">{email}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-2.5 py-2 text-xs text-subink">
            <FlaskConical size={14} /> Vai trò: <span className="font-medium text-ink">{roleLabel}</span>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onProfile();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-stem hover:bg-plate hover:text-ink"
          >
            <UserCircle size={16} /> Hồ sơ cá nhân
          </button>
          <button
            onClick={() => {
              setOpen(false);
              onSettings();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-stem hover:bg-plate hover:text-ink"
          >
            <Settings size={16} /> Cài đặt & Tài khoản
          </button>
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-overdue hover:bg-overdue/5"
          >
            <LogOut size={16} /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}
