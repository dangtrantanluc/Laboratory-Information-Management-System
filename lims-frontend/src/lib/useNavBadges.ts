import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { canApproveDocuments } from '@/lib/rbac';
import { listPendingReview } from '@/api/documents';
import type { BadgeKey } from '@/components/layout/nav';

/**
 * Số đếm động gắn trên item điều hướng (badge). Lấy số THẬT từ API, cache trong
 * state + tự làm mới định kỳ. Nguồn nào lỗi/không có quyền → bỏ badge (không giả số).
 * Mở rộng: thêm key vào BadgeKey rồi fetch tương ứng ở đây.
 */
const REFRESH_MS = 60_000;

export function useNavBadges(): Partial<Record<BadgeKey, number>> {
  const { user } = useAuth();
  const [badges, setBadges] = useState<Partial<Record<BadgeKey, number>>>({});

  useEffect(() => {
    let alive = true;
    async function load() {
      const next: Partial<Record<BadgeKey, number>> = {};
      if (canApproveDocuments(user)) {
        try {
          const res = await listPendingReview({ page: 1, limit: 1 });
          const total = res.meta?.total ?? 0;
          if (total > 0) next.approvals = total;
        } catch {
          /* endpoint lỗi → không hiện badge */
        }
      }
      if (alive) setBadges(next);
    }
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [user]);

  return badges;
}
