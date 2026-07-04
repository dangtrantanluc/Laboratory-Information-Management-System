import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/States';
import { Button } from '@/components/ui/Button';
import type { CurrentUser } from '@/types';

/** Bọc trang theo điều kiện quyền (đọc từ /auth/me). */
export function RequireAccess({
  allow,
  children,
}: {
  allow: (user: CurrentUser | null) => boolean;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  if (!allow(user)) {
    return (
      <Card>
        <EmptyState
          icon={<ShieldAlert size={22} />}
          title="Không có quyền truy cập"
          description="Bạn không được phép xem trang này. Liên hệ quản trị viên nếu cần."
          action={
            <Button variant="secondary" onClick={() => navigate('/dashboard')}>
              Về Tổng quan
            </Button>
          }
        />
      </Card>
    );
  }
  return <>{children}</>;
}
