import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { FlaskConical, LogIn } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';

export function Login() {
  const { user, loading, login, mustChangePassword } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [email, setEmail] = useState('admin@lims.local');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to={mustChangePassword ? '/change-password' : '/dashboard'} replace />;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      toast.error('Vui lòng nhập email và mật khẩu');
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate('/dashboard');
    } catch (err) {
      const { title, description } = describeError(err);
      toast.error(title, description);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-plate px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blueberry text-white">
            <FlaskConical size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-ink">LIMS</h1>
            <p className="text-sm text-subink">Hệ thống Quản lý Phòng Thí nghiệm (VILAS)</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-white p-6 shadow-card">
          <h2 className="mb-5 text-lg font-semibold text-ink">Đăng nhập</h2>
          <div className="flex flex-col gap-4">
            <Field label="Email" required>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vd: ktv@lims.local"
                autoComplete="username"
              />
            </Field>
            <Field label="Mật khẩu" required>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </Field>
            <Button type="submit" loading={submitting} className="mt-1 w-full">
              <LogIn size={16} /> Đăng nhập
            </Button>
          </div>
        </form>
        <p className="mt-4 text-center text-xs text-stem">
          Lần đầu đăng nhập sẽ được yêu cầu đổi mật khẩu.
        </p>
      </div>
    </div>
  );
}
