import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Leaf, Sprout, KeyRound, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { Field } from '@/components/ui/Field';
import { describeError } from '@/lib/errors';
import * as authApi from '@/api/auth';

/** Đặt lại mật khẩu bằng token trong mail (m30). Đặt xong, mọi phiên cũ bị thu hồi. */
export function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 8) return setError('Mật khẩu tối thiểu 8 ký tự');
    if (!/(?=.*[A-Za-z])(?=.*\d)/.test(password)) {
      return setError('Mật khẩu phải có cả chữ và số');
    }
    if (password !== confirm) return setError('Xác nhận mật khẩu không khớp');

    setError('');
    setSubmitting(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (ex) {
      setError(describeError(ex).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen-dvh items-center justify-center overflow-hidden bg-plate px-4 py-8 px-safe">
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.07]">
        <Leaf className="absolute -left-10 top-10 h-64 w-64 -rotate-12 text-blueberry" strokeWidth={0.6} />
        <Sprout className="absolute -right-8 bottom-4 h-72 w-72 rotate-6 text-blueberry" strokeWidth={0.6} />
      </div>

      <div className="relative w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <img
            src="/ribe-logo.jpeg"
            alt="RIBE"
            className="h-16 w-16 rounded-full bg-white object-contain shadow-card ring-2 ring-blueberry/20 sm:h-20 sm:w-20"
          />
          <p className="text-sm font-bold uppercase text-blueberry">
            Viện Nghiên cứu Công nghệ Sinh học và Môi trường
          </p>
        </div>

        {!token ? (
          <div className="rounded-xl border border-hairline bg-surface p-6 text-center shadow-card">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-overdue/10 text-overdue">
              <AlertTriangle size={26} />
            </div>
            <h2 className="text-lg font-semibold text-ink">Liên kết không hợp lệ</h2>
            <p className="mt-2 text-sm text-subink">
              Liên kết thiếu mã xác thực. Vui lòng mở đúng liên kết trong thư, hoặc yêu cầu
              gửi lại.
            </p>
            <Link to="/forgot-password">
              <Button className="mt-5 w-full">Yêu cầu liên kết mới</Button>
            </Link>
          </div>
        ) : done ? (
          <div className="rounded-xl border border-hairline bg-surface p-6 text-center shadow-card">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
              <CheckCircle2 size={26} />
            </div>
            <h2 className="text-lg font-semibold text-ink">Đã đổi mật khẩu</h2>
            <p className="mt-2 text-sm text-subink">
              Vì lý do an toàn, mọi thiết bị đang đăng nhập đã bị đăng xuất. Hãy đăng nhập lại
              bằng mật khẩu mới.
            </p>
            <Button className="mt-5 w-full" onClick={() => navigate('/login')}>
              Đăng nhập
            </Button>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-surface p-5 shadow-card sm:p-6">
            <h2 className="mb-1 text-lg font-semibold text-ink">Đặt mật khẩu mới</h2>
            <p className="mb-5 text-xs text-subink">
              Sau khi đổi, mọi thiết bị đang đăng nhập sẽ bị đăng xuất.
            </p>

            <div className="flex flex-col gap-4">
              <Field label="Mật khẩu mới" required hint="Tối thiểu 8 ký tự, gồm cả chữ và số">
                <PasswordInput
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  autoFocus
                />
              </Field>

              <Field label="Xác nhận mật khẩu mới" required>
                <PasswordInput
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                />
              </Field>

              {error && (
                <p className="rounded-lg bg-overdue/10 px-3 py-2 text-sm text-overdue" role="alert">
                  {error}
                </p>
              )}

              <Button type="submit" loading={submitting} className="mt-1 w-full">
                <KeyRound size={16} /> Đặt mật khẩu mới
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
