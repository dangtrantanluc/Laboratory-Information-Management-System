import { CalendarClock, Wallet, TrendingDown, Users, BarChart3, Bell, Award, FileSignature, ClipboardList } from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import { canViewCost } from '@/lib/rbac';
import { useAuth } from '@/context/AuthContext';
import { formatNumber } from '@/lib/format';
import * as reportingApi from '@/api/reporting';
import * as reportApi from '@/api/activityReport';
import * as researchApi from '@/api/research';
import * as activityApi from '@/api/activity';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec } from './DashKit';

const n = (v: any) => v ?? 0;

/** Dashboard Văn phòng — hành chính · nhân sự · tổng hợp NCKH (số thật từ các list endpoint). */
export function OfficeDashboard() {
  const { user } = useAuth();
  const showCost = canViewCost(user);
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);

  // Số thật: đọc meta.total qua limit:1 (office có quyền xem toàn bộ). Nguồn lỗi → 0.
  const aggQ = useAsync(async () => {
    const [pr, pj, pb, ct] = await Promise.allSettled([
      reportApi.listReports({ status: 'submitted', limit: 1 }),
      researchApi.listProjects({ limit: 1 }),
      researchApi.listPublications({ limit: 1 }),
      activityApi.listContracts({ limit: 1 }),
    ]);
    const total = (r: PromiseSettledResult<any>) => (r.status === 'fulfilled' ? r.value.meta?.total ?? 0 : 0);
    return { pending: total(pr), projects: total(pj), publications: total(pb), contracts: total(ct) };
  }, []);

  const data = dashQ.data?.data as any;
  const c = data?.chemicals;
  const hr = data?.hr;
  const notif = data?.notifications;
  const agg = aggQ.data ?? { pending: 0, projects: 0, publications: 0, contracts: 0 };

  const tiles: KpiSpec[] = [];
  tiles.push({ icon: <ClipboardList size={20} />, tone: 'pending', label: 'Báo cáo hoạt động chờ tổng hợp', value: agg.pending, to: '/activity-reports?status=submitted' });
  if (hr?.available) {
    tiles.push({ icon: <FileSignature size={20} />, tone: 'warning', label: 'Hợp đồng sắp hết hạn', value: n(hr.contract_ending), to: '/hr' });
    tiles.push({ icon: <CalendarClock size={20} />, tone: 'info', label: 'Đến hạn nâng lương', value: n(hr.salary_raise_due), to: '/hr' });
  }
  if (c?.available) {
    tiles.push({ icon: <CalendarClock size={20} />, tone: 'warning', label: 'Hóa chất sắp hết hạn', value: n(c.expiring_soon), to: '/chemicals' });
    tiles.push({ icon: <TrendingDown size={20} />, tone: 'overdue', label: 'Hóa chất tồn thấp', value: n(c.low_stock), to: '/chemicals' });
    if (showCost && c.consumption_cost_month !== undefined) {
      tiles.push({ icon: <Wallet size={20} />, tone: 'info', label: 'Chi phí tiêu hao (tháng)', value: formatNumber(c.consumption_cost_month) });
    }
  }
  if (notif?.available) tiles.push({ icon: <Bell size={20} />, tone: 'info', label: 'Thông báo chưa đọc', value: n(notif.unread), to: '/notifications' });

  return (
    <DashLayout
      subtitle="Hành chính · nhân sự · tổng hợp NCKH"
      onRefresh={() => { dashQ.reload(); aggQ.reload(); }}
      loading={dashQ.loading || aggQ.loading}
    >
      <QuickActions
        actions={[
          { icon: <CalendarClock size={16} />, label: 'Báo cáo hoạt động', to: '/activity-reports' },
          { icon: <Users size={16} />, label: 'Nhân sự', to: '/hr' },
          { icon: <BarChart3 size={16} />, label: 'Thống kê thành tích', to: '/research/stats' },
          { icon: <Award size={16} />, label: 'Chứng nhận đào tạo', to: '/research/certificates' },
        ]}
      />

      {dashQ.loading ? (
        <Card><CardBody><LoadingState /></CardBody></Card>
      ) : (
        <>
          <KpiGrid items={tiles} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
            <AlertList
              title="Nhân sự cần theo dõi"
              rows={[
                { label: 'Hợp đồng lao động sắp hết hạn', value: n(hr?.contract_ending), tone: 'warning', to: '/hr' },
                { label: 'Đến hạn xét nâng lương', value: n(hr?.salary_raise_due), tone: 'pending', to: '/hr' },
              ]}
            />
            <AlertList
              title="Tổng hợp thành tích NCKH (toàn hệ thống)"
              rows={[
                { label: 'Đề tài NCKH', value: agg.projects, tone: 'success', to: '/research/projects' },
                { label: 'Bài báo & sáng chế', value: agg.publications, tone: 'success', to: '/research/publications' },
                { label: 'Hợp đồng NCKH', value: agg.contracts, tone: 'success', to: '/research/contracts' },
              ]}
            />
          </div>
        </>
      )}
    </DashLayout>
  );
}
