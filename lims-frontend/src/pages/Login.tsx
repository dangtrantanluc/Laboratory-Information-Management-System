import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Leaf, Sprout, Microscope, LogIn } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { PasswordInput } from '@/components/ui/PasswordInput';
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
    <div className="relative flex min-h-screen-dvh items-center justify-center overflow-hidden bg-plate px-4 py-8 px-safe">
      {/* Motif hữu cơ (lá/tế bào) — nền trang trí, không chắn tương tác */}
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.07]">
        <Leaf className="absolute -left-10 top-10 h-64 w-64 -rotate-12 text-blueberry" strokeWidth={0.6} />
        <Sprout className="absolute -right-8 bottom-4 h-72 w-72 rotate-6 text-blueberry" strokeWidth={0.6} />
        <Microscope className="absolute right-1/4 top-4 hidden h-40 w-40 -rotate-6 text-berry sm:block" strokeWidth={0.6} />
      </div>

      <div className="relative w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <img
            src="/ribe-logo.jpeg"
            alt="Logo RIBE"
            className="h-16 w-16 rounded-full sm:h-20 sm:w-20 bg-white object-contain shadow-card ring-2 ring-blueberry/20"
          />
          <div>
            <h1 className="text-lg font-bold uppercase tracking-tight text-ink">
              Trường Đại học Nông Lâm TP. Hồ Chí Minh
            </h1>
            <p className="text-sm font-bold uppercase text-blueberry">
              Viện Nghiên cứu Công nghệ Sinh học và Môi trường
            </p>
            <p className="mt-1 text-sm text-subink">Hệ thống Quản lý Phòng Thí nghiệm (VILAS)</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-surface p-5 shadow-card sm:p-6">
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
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </Field>
            <div className="-mt-1 flex justify-end">
              <Link
                to="/forgot-password"
                className="text-xs font-medium text-blueberry hover:underline"
              >
                Quên mật khẩu?
              </Link>
            </div>
            <Button type="submit" loading={submitting} className="mt-1 w-full">
              <LogIn size={16} /> Đăng nhập
            </Button>
          </div>
        </form>
        <p className="mt-4 text-center text-sm text-subink">
          Chưa có tài khoản?{' '}
          <Link to="/register" className="font-medium text-blueberry hover:underline">
            Đăng ký
          </Link>
        </p>
        <p className="mt-2 text-center text-xs text-stem">
          Tài khoản mới cần Quản trị viên duyệt trước khi sử dụng.
        </p>
      </div>
    </div>
  );
}
