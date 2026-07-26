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
 * Chi tiết hồ sơ nhân sự cho admin/leader/office.
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
