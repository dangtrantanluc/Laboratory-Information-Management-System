import { useState } from 'react';
import { Monitor, Smartphone, LogOut, ShieldCheck } from 'lucide-react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import * as authApi from '@/api/auth';

/**
 * Danh sách thiết bị đang đăng nhập (m30).
 *
 * Thu hồi một phiên chỉ chặn việc GIA HẠN — access token đang cầm vẫn sống tối đa
 * 30 phút (JWT stateless). Giao diện nói rõ điều đó để người dùng không hiểu nhầm
 * là thiết bị kia bị ngắt tức thì.
 */
export function SessionList() {
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => authApi.listSessions(), []);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [busy, setBusy] = useState(false);

  const sessions = data ?? [];
  const otherCount = sessions.filter((s) => !s.is_current).length;

  async function revokeOne(id: string) {
    setBusy(true);
    try {
      await authApi.revokeSession(id);
      toast.success('Đã đăng xuất thiết bị');
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
      setRevoking(null);
    }
  }

  async function revokeAll() {
    setBusy(true);
    try {
      const r = await authApi.revokeOtherSessions();
      toast.success(`Đã đăng xuất ${r.revoked_count} thiết bị khác`);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
      setConfirmAll(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Thiết bị đang đăng nhập"
        subtitle="Kiểm tra và đăng xuất từ xa những phiên bạn không nhận ra"
        action={
          otherCount > 0 ? (
            <Button size="sm" variant="secondary" onClick={() => setConfirmAll(true)}>
              <LogOut size={14} /> Đăng xuất thiết bị khác
            </Button>
          ) : undefined
        }
      />
      <CardBody className="p-0">
        {loading ? (
          <LoadingState label="Đang tải danh sách phiên…" />
        ) : sessions.length === 0 ? (
          <EmptyState title="Không có phiên nào đang hoạt động" />
        ) : (
          <ul className="divide-y divide-hairline">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-col gap-3 px-5 py-3.5 sm:flex-row sm:items-center">
                <div
                  className={
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ' +
                    (s.is_current ? 'bg-success/10 text-success' : 'bg-stem/10 text-stem')
                  }
                >
                  {s.is_mobile ? <Smartphone size={18} /> : <Monitor size={18} />}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                    {s.device}
                    {s.is_current && (
                      <Badge tone="success">
                        <ShieldCheck size={11} /> Thiết bị này
                      </Badge>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-subink">
                    {s.ip ? `IP ${s.ip} · ` : ''}Đăng nhập {formatDateTime(s.created_at)}
                  </p>
                </div>

                {!s.is_current && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => setRevoking(s.id)}
                    className="shrink-0 text-overdue hover:bg-overdue/10"
                  >
                    <LogOut size={14} /> Đăng xuất
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        <p className="border-t border-hairline px-5 py-3 text-xs text-stem">
          Thiết bị bị đăng xuất sẽ không gia hạn được phiên và ngừng truy cập trong vòng tối đa
          30 phút.
        </p>
      </CardBody>

      <ConfirmDialog
        open={!!revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoking && revokeOne(revoking)}
        title="Đăng xuất thiết bị này?"
        message="Thiết bị đó sẽ phải đăng nhập lại. Thao tác này không ảnh hưởng tới phiên hiện tại của bạn."
        confirmText="Đăng xuất"
        loading={busy}
      />

      <ConfirmDialog
        open={confirmAll}
        onClose={() => setConfirmAll(false)}
        onConfirm={revokeAll}
        title="Đăng xuất mọi thiết bị khác?"
        message={`${otherCount} thiết bị khác sẽ bị đăng xuất. Phiên hiện tại của bạn vẫn giữ nguyên.`}
        confirmText="Đăng xuất tất cả"
        loading={busy}
      />
    </Card>
  );
}
