import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import * as authApi from '@/api/auth';
import { getToken, setToken, setOnSessionExpired } from '@/lib/api';
import type { CurrentUser, Role } from '@/types';

interface AuthCtx {
  user: CurrentUser | null;
  role: Role | null;
  loading: boolean;
  /** true sau login khi backend yêu cầu đổi mật khẩu lần đầu. */
  mustChangePassword: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
  updateProfile: (body: authApi.UpdateMeBody) => Promise<void>;
  refreshMe: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  const loadMe = useCallback(async () => {
    try {
      const me = await authApi.getMe();
      setUser(me);
      setMustChangePassword(!!me.must_change_password);
    } catch {
      setUser(null);
      setToken(null);
    }
  }, []);

  // Khôi phục phiên khi reload nếu còn token (hoặc cookie refresh).
  useEffect(() => {
    (async () => {
      if (getToken()) {
        await loadMe();
      }
      setLoading(false);
    })();
  }, [loadMe]);

  // Khi refresh token fail hoàn toàn → đăng xuất.
  useEffect(() => {
    setOnSessionExpired(() => {
      setUser(null);
      setMustChangePassword(false);
    });
    return () => setOnSessionExpired(null);
  }, []);

  const login = useCallback<AuthCtx['login']>(async (email, password) => {
    const res = await authApi.login(email, password);
    setMustChangePassword(!!res.must_change_password);
    await loadMe();
  }, [loadMe]);

  const logout = useCallback<AuthCtx['logout']>(async () => {
    await authApi.logout();
    setUser(null);
    setMustChangePassword(false);
  }, []);

  const changePassword = useCallback<AuthCtx['changePassword']>(async (current, next) => {
    await authApi.changePassword(current, next);
    setMustChangePassword(false);
    await loadMe();
  }, [loadMe]);

  const updateProfile = useCallback<AuthCtx['updateProfile']>(async (body) => {
    await authApi.updateMe(body);
    await loadMe();
  }, [loadMe]);

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      role: user?.role ?? null,
      loading,
      mustChangePassword,
      login,
      logout,
      changePassword,
      updateProfile,
      refreshMe: loadMe,
    }),
    [user, loading, mustChangePassword, login, logout, changePassword, updateProfile, loadMe],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
