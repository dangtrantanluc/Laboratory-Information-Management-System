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
    // Chỉ gọi khi tab đang hiện. Tab để nền cả ngày trước đây vẫn bắn ~60 request/giờ,
    // và — quan trọng hơn — chính nhịp này bảo đảm MỌI tab chạm 401 gần như cùng lúc
    // khi access token hết hạn, kích hoạt đua refresh (xem lib/api.ts doRefresh).
    const tick = () => {
      if (document.visibilityState === 'visible') load();
    };
    tick();
    const id = setInterval(tick, REFRESH_MS);
    // Quay lại tab → làm mới ngay, không bắt người dùng chờ hết chu kỳ.
    document.addEventListener('visibilitychange', tick);
    return () => {
      alive = false;
      clearInterval(id);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [user]);

  return badges;
}
