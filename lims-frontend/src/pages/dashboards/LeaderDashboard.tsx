import { ClipboardList, AlertTriangle, CheckCircle2, Wrench, CalendarClock, FileText, Wallet, BarChart3, Users, ScrollText, ShieldAlert } from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import { useAuth } from '@/context/AuthContext';
import { canViewCost } from '@/lib/rbac';
import { formatNumber } from '@/lib/format';
import * as reportingApi from '@/api/reporting';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec, type QuickAction } from './DashKit';
import { SamplesByStatusCard, SamplesOverTimeCard, ChemicalConsumptionCard } from './DashCharts';

const n = (v: any) => v ?? 0;

/** Dashboard Ban giám đốc / Quản trị — điều hành cấp cao, nhìn toàn cảnh. */
export function LeaderDashboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const showCost = canViewCost(user);
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const chartsQ = useAsync(() => reportingApi.getDashboardCharts(), []);
  const data = dashQ.data?.data as any;
  const charts = chartsQ.data?.data as any;
  const s = data?.samples;
  const c = data?.chemicals;
  const e = data?.equipments;
  const hr = data?.hr;
  const doc = data?.documents;

  const tiles: KpiSpec[] = [];
  if (s?.available) {
    tiles.push({ icon: <ClipboardList size={20} />, tone: 'info', label: 'Tổng mẫu', value: n(s.total), to: '/samples' });
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Mẫu quá hạn', value: n(s.overdue), to: '/samples?status=overdue' });
    tiles.push({ icon: <CheckCircle2 size={20} />, tone: 'success', label: 'Đã chốt', value: n(s.by_status?.done) });
  }
  if (e?.available) tiles.push({ icon: <Wrench size={20} />, tone: 'overdue', label: 'Thiết bị quá hạn hiệu chuẩn', value: n(e.calibration_overdue), to: '/equipment' });
  if (c?.available) {
    tiles.push({ icon: <CalendarClock size={20} />, tone: 'warning', label: 'Hóa chất sắp hết hạn', value: n(c.expiring_soon), to: '/chemicals' });
    if (showCost && c.consumption_cost_month !== undefined) {
      tiles.push({ icon: <Wallet size={20} />, tone: 'info', label: 'Chi phí tiêu hao (tháng)', value: formatNumber(c.consumption_cost_month) });
    }
  }
  if (hr?.available) tiles.push({ icon: <Users size={20} />, tone: 'warning', label: 'Nhân sự: HĐ/nâng lương tới hạn', value: n(hr.salary_raise_due) + n(hr.contract_ending), to: '/hr' });
  if (doc?.available) tiles.push({ icon: <FileText size={20} />, tone: 'pending', label: 'Tài liệu chờ duyệt', value: n(doc.pending_review), to: '/documents/pending' });

  const actions: QuickAction[] = [
    { icon: <BarChart3 size={16} />, label: 'Báo cáo tổng hợp', to: '/reports' },
    { icon: <ClipboardList size={16} />, label: 'Mẫu', to: '/samples' },
    { icon: <ShieldAlert size={16} />, label: 'Không phù hợp', to: '/nonconformities' },
  ];
  if (isAdmin) {
    actions.push({ icon: <Users size={16} />, label: 'Tài khoản', to: '/users' });
    actions.push({ icon: <ScrollText size={16} />, label: 'Nhật ký hệ thống', to: '/audit' });
  }

  return (
    <DashLayout
      subtitle={isAdmin ? 'Điều hành & vận hành hệ thống toàn cục' : 'Bức tranh điều hành toàn phòng thí nghiệm'}
      onRefresh={() => { dashQ.reload(); chartsQ.reload(); }}
      loading={dashQ.loading || chartsQ.loading}
    >
      <QuickActions actions={actions} />

      {dashQ.loading ? (
        <Card><CardBody><LoadingState /></CardBody></Card>
      ) : (
        <>
          <KpiGrid items={tiles} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
            <SamplesByStatusCard charts={charts} loading={chartsQ.loading} />
            <SamplesOverTimeCard charts={charts} loading={chartsQ.loading} />
            <AlertList
              title="Cảnh báo tổng hợp"
              rows={[
                { label: 'Mẫu quá hạn', value: n(s?.overdue), tone: 'overdue', to: '/samples?status=overdue' },
                { label: 'Thiết bị quá hạn hiệu chuẩn', value: n(e?.calibration_overdue), tone: 'overdue', to: '/equipment' },
                { label: 'Hóa chất tồn thấp', value: n(c?.low_stock), tone: 'warning', to: '/chemicals' },
                { label: 'Tài liệu chờ ban hành', value: n(doc?.pending_review), tone: 'pending', to: '/documents/pending' },
              ]}
            />
            <ChemicalConsumptionCard charts={charts} loading={chartsQ.loading} />
          </div>
        </>
      )}
    </DashLayout>
  );
}
