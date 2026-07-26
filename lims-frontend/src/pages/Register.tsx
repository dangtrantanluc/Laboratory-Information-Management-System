import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Leaf, Sprout, UserPlus, MailCheck, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { Field, Input } from '@/components/ui/Field';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import * as authApi from '@/api/auth';

/**
 * Đăng ký tài khoản (m30).
 *
 * Tài khoản tạo ra LUÔN ở trạng thái chờ duyệt — trang này nói rõ điều đó ngay từ
 * đầu để người dùng không tưởng đăng ký xong là vào được ngay.
 */
export function Register() {
  const navigate = useNavigate();
  const { data: config, loading: loadingConfig } = useAsync(
    () => authApi.getRegistrationConfig(),
    [],
  );

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);

  const domains = config?.allowed_domains ?? [];

  function validate(): string | null {
    if (fullName.trim().length < 2) return 'Vui lòng nhập họ tên đầy đủ';
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return 'Địa chỉ email không hợp lệ';
    if (domains.length > 0) {
      const d = email.split('@')[1]?.toLowerCase() ?? '';
      if (!domains.includes(d)) {
        return `Chỉ chấp nhận email thuộc: ${domains.map((x) => '@' + x).join(', ')}`;
      }
    }
    if (password.length < 8) return 'Mật khẩu tối thiểu 8 ký tự';
    if (!/(?=.*[A-Za-z])(?=.*\d)/.test(password)) return 'Mật khẩu phải có cả chữ và số';
    if (password !== confirm) return 'Xác nhận mật khẩu không khớp';
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) return setError(err);
    setError('');
    setSubmitting(true);
    try {
      await authApi.register({ email: email.trim(), full_name: fullName.trim(), password });
      // Backend luôn trả cùng thông điệp — không tiết lộ email đã tồn tại hay chưa.
      setSentTo(email.trim());
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
          <div>
            <h1 className="text-lg font-bold uppercase tracking-tight text-ink">
              Trường Đại học Nông Lâm TP. Hồ Chí Minh
            </h1>
            <p className="text-sm font-bold uppercase text-blueberry">
              Viện Nghiên cứu Công nghệ Sinh học và Môi trường
            </p>
          </div>
        </div>

        {sentTo ? (
          /* ── Đã gửi thư xác thực ── */
          <div className="rounded-xl border border-hairline bg-surface p-5 text-center shadow-card sm:p-6">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
              <MailCheck size={26} />
            </div>
            <h2 className="text-lg font-semibold text-ink">Kiểm tra hộp thư của bạn</h2>
            <p className="mt-2 text-sm text-subink">
              Nếu địa chỉ <strong className="text-ink">{sentTo}</strong> hợp lệ, chúng tôi đã gửi
              thư kèm liên kết xác thực. Liên kết có hiệu lực trong 24 giờ.
            </p>
            <div className="mt-4 rounded-lg bg-plate p-3 text-left text-xs text-subink">
              <p className="font-semibold text-ink">Các bước tiếp theo</p>
              <ol className="mt-1.5 list-decimal space-y-1 pl-4">
                <li>Mở liên kết trong thư để xác thực email</li>
                <li>Quản trị viên duyệt và gán vai trò cho bạn</li>
                <li>Bạn nhận thư thông báo và có thể đăng nhập</li>
              </ol>
            </div>
            <p className="mt-3 text-xs text-stem">
              Không thấy thư? Kiểm tra mục Spam / Quảng cáo.
            </p>
            <Button className="mt-5 w-full" onClick={() => navigate('/login')}>
              <ArrowLeft size={16} /> Về trang đăng nhập
            </Button>
          </div>
        ) : loadingConfig ? (
          <div className="rounded-xl border border-hairline bg-surface p-6 text-center text-sm text-subink shadow-card">
            Đang tải…
          </div>
        ) : config && !config.enabled ? (
          /* ── Admin đã tắt đăng ký tự phục vụ ── */
          <div className="rounded-xl border border-hairline bg-surface p-6 text-center shadow-card">
            <h2 className="text-lg font-semibold text-ink">Đăng ký đang tạm đóng</h2>
            <p className="mt-2 text-sm text-subink">
              Hệ thống hiện không mở đăng ký tự phục vụ. Vui lòng liên hệ Văn phòng Viện để
              được cấp tài khoản.
            </p>
            <Link to="/login">
              <Button variant="secondary" className="mt-5 w-full">
                <ArrowLeft size={16} /> Về trang đăng nhập
              </Button>
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="rounded-xl border border-hairline bg-surface p-5 shadow-card sm:p-6">
            <h2 className="mb-1 text-lg font-semibold text-ink">Đăng ký tài khoản</h2>
            <p className="mb-5 text-xs text-subink">
              Tài khoản sẽ được Quản trị viên duyệt và gán vai trò trước khi sử dụng.
            </p>

            <div className="flex flex-col gap-4">
              <Field label="Họ và tên" required>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nguyễn Văn A"
                  autoComplete="name"
                />
              </Field>

              <Field
                label="Email"
                required
                hint={
                  domains.length > 0
                    ? `Chỉ chấp nhận: ${domains.map((d) => '@' + d).join(', ')}`
                    : 'Dùng để đăng nhập và nhận thư xác thực'
                }
              >
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ten.ban@hcmuaf.edu.vn"
                  autoComplete="email"
                />
              </Field>

              <Field label="Mật khẩu" required hint="Tối thiểu 8 ký tự, gồm cả chữ và số">
                <PasswordInput
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </Field>

              <Field label="Xác nhận mật khẩu" required>
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
                <UserPlus size={16} /> Tạo tài khoản
              </Button>
            </div>
          </form>
        )}

        {!sentTo && (
          <p className="mt-4 text-center text-sm text-subink">
            Đã có tài khoản?{' '}
            <Link to="/login" className="font-medium text-blueberry hover:underline">
              Đăng nhập
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
