import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Leaf, Sprout, KeyRound, MailCheck, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { describeError } from '@/lib/errors';
import * as authApi from '@/api/auth';

/**
 * Quên mật khẩu (m30).
 *
 * Backend luôn trả cùng một thông điệp dù email có tồn tại hay không, nên màn hình
 * này KHÔNG được nói "email không tồn tại" — làm vậy là mở đường cho việc dò danh
 * sách người dùng của hệ thống.
 */
export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      return setError('Địa chỉ email không hợp lệ');
    }
    setError('');
    setSubmitting(true);
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
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

        {sent ? (
          <div className="rounded-xl border border-hairline bg-surface p-5 text-center shadow-card sm:p-6">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
              <MailCheck size={26} />
            </div>
            <h2 className="text-lg font-semibold text-ink">Đã gửi hướng dẫn</h2>
            <p className="mt-2 text-sm text-subink">
              Nếu <strong className="text-ink">{email}</strong> tồn tại trong hệ thống, chúng tôi
              đã gửi liên kết đặt lại mật khẩu. Liên kết có hiệu lực{' '}
              <strong className="text-ink">30 phút</strong> và chỉ dùng được một lần.
            </p>
            <p className="mt-3 text-xs text-stem">Không thấy thư? Kiểm tra mục Spam / Quảng cáo.</p>
            <Link to="/login">
              <Button variant="secondary" className="mt-5 w-full">
                <ArrowLeft size={16} /> Về trang đăng nhập
              </Button>
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-surface p-5 shadow-card sm:p-6">
            <h2 className="mb-1 text-lg font-semibold text-ink">Quên mật khẩu</h2>
            <p className="mb-5 text-xs text-subink">
              Nhập email đăng nhập, chúng tôi sẽ gửi liên kết đặt lại mật khẩu.
            </p>

            <div className="flex flex-col gap-4">
              <Field label="Email" required>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ten.ban@hcmuaf.edu.vn"
                  autoComplete="email"
                  autoFocus
                />
              </Field>

              {error && (
                <p className="rounded-lg bg-overdue/10 px-3 py-2 text-sm text-overdue" role="alert">
                  {error}
                </p>
              )}

              <Button type="submit" loading={submitting} className="mt-1 w-full">
                <KeyRound size={16} /> Gửi liên kết đặt lại
              </Button>
            </div>
          </form>
        )}

        {!sent && (
          <p className="mt-4 text-center text-sm text-subink">
            Nhớ ra rồi?{' '}
            <Link to="/login" className="font-medium text-blueberry hover:underline">
              Quay lại đăng nhập
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
