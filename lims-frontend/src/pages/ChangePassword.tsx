import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';

export function ChangePassword() {
  const { user, loading, mustChangePassword, changePassword } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && !user) return <Navigate to="/login" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 8) {
      toast.error('Mật khẩu mới tối thiểu 8 ký tự');
      return;
    }
    if (next !== confirm) {
      toast.error('Xác nhận mật khẩu không khớp');
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      toast.success('Đổi mật khẩu thành công');
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
            <KeyRound size={26} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-ink">Đổi mật khẩu</h1>
            <p className="text-sm text-subink">
              {mustChangePassword
                ? 'Lần đầu đăng nhập — vui lòng đặt mật khẩu mới để tiếp tục.'
                : 'Cập nhật mật khẩu tài khoản của bạn.'}
            </p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-white p-6 shadow-card">
          <div className="flex flex-col gap-4">
            <Field label="Mật khẩu hiện tại" required>
              <Input
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
              />
            </Field>
            <Field label="Mật khẩu mới" required hint="Tối thiểu 8 ký tự">
              <Input
                type="password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                autoComplete="new-password"
              />
            </Field>
            <Field label="Xác nhận mật khẩu mới" required>
              <Input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
              />
            </Field>
            <Button type="submit" loading={submitting} className="mt-1 w-full">
              Đổi mật khẩu
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
