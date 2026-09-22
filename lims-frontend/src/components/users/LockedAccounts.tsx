import { useState } from 'react';
import { LockKeyhole, ShieldAlert, Unlock, RefreshCw } from 'lucide-react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import * as usersApi from '@/api/users';
import type { LockoutEntry } from '@/api/users';

/**
 * Tài khoản bị khoá đăng nhập (m49).
 *
 * VÌ SAO Ở ĐÂY, KHÔNG PHẢI MỘT MỤC MENU RIÊNG
 * Phần lớn thời gian danh sách này rỗng. Một mục menu luôn hiện mà 99% thời gian
 * không có gì là thứ người ta học cách bỏ qua — đúng lúc cần thì không ai nhớ tới nó.
 * Đặt ngay trong màn hình Tài khoản thì quản trị viên gặp nó ở đúng nơi họ đã tới khi
 * có người báo "không đăng nhập được".
 *
 * KHOÁ NẰM Ở REDIS VÀ TỰ HẾT HẠN
 * Đây là ảnh chụp hiện tại, không phải lịch sử. Lịch sử nằm ở Nhật ký hệ thống với
 * hành động ACCOUNT_LOCKED / ACCOUNT_UNLOCKED.
 */
export function LockedAccounts({ onChanged }: { onChanged?: () => void }) {
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => usersApi.listLockouts(), []);
  const [busy, setBusy] = useState<string | null>(null);

  const locked = data?.locked ?? [];
  const failing = data?.failing ?? [];

  async function unlock(e: LockoutEntry) {
    if (!e.user_id) return;
    setBusy(e.user_id);
    try {
      await usersApi.unlockUser(e.user_id);
      toast.success(`Đã mở khoá ${e.full_name ?? e.email}`, 'Người dùng đăng nhập lại được ngay.');
      reload();
      onChanged?.();
    } catch (err) {
      const d = describeError(err);
      toast.error(d.title, d.description);
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <LoadingState />;

  return (
    <Card>
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <LockKeyhole size={16} /> Tài khoản bị khoá đăng nhập
          </span>
        }
        subtitle={
          locked.length === 0 && failing.length === 0
            ? 'Hiện không có tài khoản nào bị khoá.'
            : 'Khoá đặt theo từng địa chỉ IP và tự hết hạn. Mở khoá để người dùng vào lại ngay.'
        }
        action={
          <Button variant="secondary" size="sm" onClick={reload}>
            <RefreshCw size={14} /> Làm mới
          </Button>
        }
      />
      <CardBody>
        {locked.length === 0 && failing.length === 0 ? (
          <p className="text-sm text-subink">
            Tài khoản bị khoá tạm thời sau khi nhập sai mật khẩu nhiều lần liên tiếp.
            Khi có, chúng sẽ hiện ở đây kèm nút mở khoá.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {locked.length > 0 && (
              <Section
                tone="overdue"
                title={`Đang bị khoá · ${locked.length}`}
                rows={locked}
                busy={busy}
                onUnlock={unlock}
              />
            )}
            {failing.length > 0 && (
              <Section
                tone="warning"
                title={`Đang nhập sai, chưa bị khoá · ${failing.length}`}
                hint="Cảnh báo sớm: nhiều lần sai liên tiếp trên một email lạ là dấu hiệu dò mật khẩu."
                rows={failing}
                busy={busy}
                onUnlock={unlock}
              />
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Section({
  title, hint, rows, tone, busy, onUnlock,
}: {
  title: string;
  hint?: string;
  rows: LockoutEntry[];
  tone: 'overdue' | 'warning';
  busy: string | null;
  onUnlock: (e: LockoutEntry) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Badge tone={tone}>{title}</Badge>
        {hint && <span className="text-xs text-subink">{hint}</span>}
      </div>
      <div className="flex flex-col divide-y divide-hairline rounded-lg border border-hairline">
        {rows.map((e) => (
          <div
            key={`${e.email}|${e.ip}`}
            className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium text-ink">
                  {e.full_name ?? e.email}
                </span>
                {!e.is_known_account && (
                  <Badge tone="overdue">
                    <ShieldAlert size={12} /> Email không có tài khoản
                  </Badge>
                )}
              </div>
              <div className="text-xs text-subink">
                {e.full_name ? `${e.email} · ` : ''}
                IP {e.ip}
                {typeof e.failed_attempts === 'number' && e.failed_attempts > 0
                  ? ` · ${e.failed_attempts} lần sai`
                  : ''}
                {e.remaining_seconds > 0 ? ` · còn ${fmtLeft(e.remaining_seconds)}` : ''}
              </div>
            </div>
            {/* Không có tài khoản thì không có gì để mở khoá — khoá sẽ tự hết hạn.
                Vẫn hiện dòng đó, vì nó là dấu hiệu bị dò email. */}
            {e.user_id ? (
              <Button
                size="sm"
                variant="secondary"
                loading={busy === e.user_id}
                onClick={() => onUnlock(e)}
              >
                <Unlock size={14} /> Mở khoá
              </Button>
            ) : (
              <span className="text-xs italic text-subink">tự hết hạn</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** "còn 7 phút" dễ đọc hơn "còn 438 giây" khi người dùng đang chờ. */
function fmtLeft(seconds: number): string {
  if (seconds < 60) return `${seconds} giây`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m} phút ${s} giây` : `${m} phút`;
}
