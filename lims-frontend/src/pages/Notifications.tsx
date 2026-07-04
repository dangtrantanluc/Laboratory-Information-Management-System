import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import * as notifApi from '@/api/notifications';
import type { Notification } from '@/types';

export function Notifications() {
  const navigate = useNavigate();
  const toast = useToast();
  const [onlyUnread, setOnlyUnread] = useState(false);
  const { data, loading, reload } = useAsync(
    () => notifApi.listNotifications({ unread: onlyUnread || undefined, limit: 100 }),
    [onlyUnread],
  );

  async function onClick(n: Notification) {
    try {
      if (!n.read_at) await notifApi.markRead(n.id);
    } catch {
      /* ignore */
    }
    if (n.ref_type === 'sample' && n.ref_id) navigate(`/samples/sample/${n.ref_id}`);
    else reload();
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Thông báo"
        description="Cập nhật nghiệp vụ liên quan đến bạn"
        icon={<Bell size={20} />}
        actions={
          <Button
            variant="secondary"
            onClick={async () => {
              try {
                await notifApi.markAllRead();
                toast.success('Đã đánh dấu tất cả là đã đọc');
                reload();
              } catch (err) {
                toast.error(describeError(err).title);
              }
            }}
          >
            <CheckCheck size={16} /> Đánh dấu đã đọc hết
          </Button>
        }
      />
      <div className="flex gap-2">
        <Button size="sm" variant={onlyUnread ? 'ghost' : 'primary'} onClick={() => setOnlyUnread(false)}>
          Tất cả
        </Button>
        <Button size="sm" variant={onlyUnread ? 'primary' : 'ghost'} onClick={() => setOnlyUnread(true)}>
          Chưa đọc
        </Button>
      </div>

      <Card>
        <CardBody className="p-0">
          {loading ? (
            <LoadingState />
          ) : (data?.data ?? []).length === 0 ? (
            <EmptyState title="Không có thông báo" />
          ) : (
            <ul className="flex flex-col divide-y divide-hairline">
              {(data?.data ?? []).map((n) => (
                <li
                  key={n.id}
                  onClick={() => onClick(n)}
                  className="flex cursor-pointer items-start gap-3 px-5 py-4 hover:bg-plate/60"
                >
                  {!n.read_at ? (
                    <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-blueberry" />
                  ) : (
                    <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-hairline" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">{n.title}</p>
                    <p className="text-sm text-subink">{n.body}</p>
                    <p className="mt-1 text-xs text-stem">{formatDateTime(n.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
