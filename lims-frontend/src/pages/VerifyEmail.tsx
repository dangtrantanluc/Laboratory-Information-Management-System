import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Leaf, Sprout, CheckCircle2, AlertTriangle, Clock3 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/States';
import { describeError } from '@/lib/errors';
import * as authApi from '@/api/auth';

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; awaitingApproval: boolean; alreadyVerified: boolean }
  | { kind: 'error'; message: string };

/** Xác thực email từ liên kết trong thư (m30). */
export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [state, setState] = useState<State>({ kind: 'loading' });
  // StrictMode ở dev gọi effect 2 lần; token dùng-một-lần nên lần 2 sẽ báo "đã dùng".
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current) return;
    firedRef.current = true;

    if (!token) {
      setState({ kind: 'error', message: 'Liên kết thiếu mã xác thực.' });
      return;
    }
    authApi
      .verifyEmail(token)
      .then((r) =>
        setState({
          kind: 'ok',
          awaitingApproval: r.awaiting_approval,
          alreadyVerified: r.already_verified,
        }),
      )
      .catch((ex) => setState({ kind: 'error', message: describeError(ex).title }));
  }, [token]);

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

        <div className="rounded-xl border border-hairline bg-surface p-6 text-center shadow-card">
          {state.kind === 'loading' && (
            <>
              <div className="flex justify-center py-2">
                <Spinner className="h-8 w-8" />
              </div>
              <p className="mt-2 text-sm text-subink">Đang xác thực địa chỉ email…</p>
            </>
          )}

          {state.kind === 'ok' && (
            <>
              <div
                className={
                  'mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full ' +
                  (state.awaitingApproval
                    ? 'bg-pending/10 text-pending'
                    : 'bg-success/10 text-success')
                }
              >
                {state.awaitingApproval ? <Clock3 size={26} /> : <CheckCircle2 size={26} />}
              </div>
              <h2 className="text-lg font-semibold text-ink">
                {state.alreadyVerified ? 'Email đã được xác thực trước đó' : 'Xác thực thành công'}
              </h2>

              {state.awaitingApproval ? (
                <>
                  <p className="mt-2 text-sm text-subink">
                    Địa chỉ email của bạn đã được xác nhận. Tài khoản hiện{' '}
                    <strong className="text-ink">đang chờ Quản trị viên duyệt</strong> và gán vai trò.
                  </p>
                  <p className="mt-3 rounded-lg bg-plate p-3 text-xs text-subink">
                    Bạn sẽ nhận được thư thông báo ngay khi tài khoản được kích hoạt. Chưa thể
                    đăng nhập ở bước này.
                  </p>
                </>
              ) : (
                <p className="mt-2 text-sm text-subink">
                  Tài khoản của bạn đã sẵn sàng. Hãy đăng nhập để bắt đầu sử dụng.
                </p>
              )}

              <Link to="/login">
                <Button variant={state.awaitingApproval ? 'secondary' : 'primary'} className="mt-5 w-full">
                  Về trang đăng nhập
                </Button>
              </Link>
            </>
          )}

          {state.kind === 'error' && (
            <>
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-overdue/10 text-overdue">
                <AlertTriangle size={26} />
              </div>
              <h2 className="text-lg font-semibold text-ink">Không xác thực được</h2>
              <p className="mt-2 text-sm text-subink">{state.message}</p>
              <p className="mt-3 text-xs text-stem">
                Liên kết xác thực có hiệu lực 24 giờ và chỉ dùng được một lần. Nếu đã hết hạn,
                hãy đăng ký lại bằng cùng địa chỉ email để nhận thư mới.
              </p>
              <div className="mt-5 flex flex-col gap-2">
                <Link to="/register">
                  <Button className="w-full">Gửi lại thư xác thực</Button>
                </Link>
                <Link to="/login">
                  <Button variant="secondary" className="w-full">
                    Về trang đăng nhập
                  </Button>
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
