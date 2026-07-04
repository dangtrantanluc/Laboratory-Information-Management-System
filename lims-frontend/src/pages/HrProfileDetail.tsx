import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, UserSquare2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { canManageHr, canEditSalary, canViewCompetence, canManageCompetence } from '@/lib/rbac';
import * as hrApi from '@/api/hr';
import { HrProfileView } from '@/components/hr/HrProfileView';

/**
 * Chi tiết hồ sơ nhân sự cho admin/leader/accountant.
 * Field-level strip do BE thực hiện; FE chỉ hiển thị field nếu `'field' in profile`.
 */
export function HrProfileDetail() {
  const { userId = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const profileQ = useAsync(() => hrApi.getProfile(userId), [userId]);

  if (profileQ.loading) return <LoadingState />;
  const profile = profileQ.data;
  if (!profile)
    return (
      <Card>
        <EmptyState title="Không tìm thấy hồ sơ nhân sự" />
      </Card>
    );

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/hr')}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Danh sách nhân sự
      </button>

      <PageHeader
        title={profile.full_name}
        description={`${profile.department_name ?? 'Chưa có phòng'}${profile.job_title ? ` · ${profile.job_title}` : ''}`}
        icon={<UserSquare2 size={20} />}
      />

      <HrProfileView
        userId={userId}
        profile={profile}
        onProfileChange={() => profileQ.reload()}
        canManage={canManageHr(user)}
        canEditSalary={canEditSalary(user)}
        canViewCompetence={canViewCompetence(user)}
        canManageCompetence={canManageCompetence(user)}
      />
    </div>
  );
}

/** Hồ sơ của chính mình — mọi vai trò xem được, có đủ lương/HĐ/PII của mình. */
export function MyProfile() {
  const { user } = useAuth();
  const profileQ = useAsync(() => hrApi.getMyProfile(), []);
  const [missing, setMissing] = useState(false);

  if (profileQ.loading) return <LoadingState />;
  const profile = profileQ.data;
  if (!profile || missing)
    return (
      <div className="flex flex-col gap-5">
        <PageHeader title="Hồ sơ của tôi" icon={<UserSquare2 size={20} />} />
        <Card>
          <EmptyState
            title="Bạn chưa có hồ sơ nhân sự"
            description="Liên hệ Kế toán hoặc Quản trị viên để được khởi tạo hồ sơ."
          />
        </Card>
      </div>
    );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hồ sơ của tôi"
        description={`${profile.department_name ?? 'Chưa có phòng'}${profile.job_title ? ` · ${profile.job_title}` : ''}`}
        icon={<UserSquare2 size={20} />}
      />
      <HrProfileView
        userId={profile.user_id}
        profile={profile}
        onProfileChange={() => profileQ.reload()}
        // Chính chủ chỉ XEM (không tự nâng lương/sửa HĐ) trừ khi là admin/accountant
        canManage={false}
        canEditSalary={user?.role === 'admin' || user?.role === 'accountant'}
        canViewCompetence
        canManageCompetence={user?.role === 'admin' || user?.role === 'leader'}
        selfView
        onNotFound={() => setMissing(true)}
      />
    </div>
  );
}
