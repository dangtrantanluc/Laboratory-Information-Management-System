import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { getLastCorrelationId } from '@/lib/api';

interface State {
  error: Error | null;
}

/**
 * Chặn lỗi render lan ra toàn cây (R5.1).
 *
 * Không có nó, một chỗ đọc `user.department.name` với `department === null` sẽ
 * unmount TOÀN BỘ app → màn hình trắng hoàn toàn, người dùng không có nút nào để
 * bấm, không biết chuyện gì xảy ra, phải tự đoán là F5.
 *
 * Hiển thị mã sự cố (correlation-id của request gần nhất) để người dùng đọc cho
 * quản trị viên tra đúng dòng log.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // TODO(R9.3): đẩy về hệ thống giám sát khi có hạ tầng
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    const cid = getLastCorrelationId();
    return (
      <div className="flex min-h-screen-dvh flex-col items-center justify-center gap-4 bg-plate px-4 py-8 text-center px-safe">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-overdue/10 text-overdue">
          <AlertTriangle size={26} />
        </div>

        <div className="max-w-md">
          <h1 className="text-lg font-semibold text-ink">Đã xảy ra lỗi hiển thị</h1>
          <p className="mt-1 text-sm text-subink">
            Trang không tải được. Dữ liệu của bạn không bị ảnh hưởng.
          </p>
          {cid && (
            <p className="mt-3 rounded-lg bg-surface px-3 py-2 text-xs text-stem">
              Mã sự cố: <code className="font-mono text-ink">{cid}</code>
              <br />
              Vui lòng gửi mã này cho Quản trị viên.
            </p>
          )}
        </div>

        <div className="flex flex-wrap justify-center gap-2">
          <Button onClick={() => window.location.reload()}>
            <RotateCcw size={16} /> Tải lại trang
          </Button>
          <Button variant="secondary" onClick={() => (window.location.href = '/dashboard')}>
            Về trang chủ
          </Button>
        </div>
      </div>
    );
  }
}
