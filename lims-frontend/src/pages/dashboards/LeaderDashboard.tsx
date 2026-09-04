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
  const it = data?.intakes;  // m39 — luồng nhận mẫu đang chạy thật
  const c = data?.chemicals;
  const e = data?.equipments;
  const hr = data?.hr;
  const doc = data?.documents;

  const tiles: KpiSpec[] = [];
  // m39 — luồng nhận mẫu đang chạy thật (sample_intakes) đứng TRƯỚC, vì đó là thứ
  // quầy ghi vào hằng ngày. Khối `samples` của module M1 giữ song song bên dưới với
  // nhãn riêng: hai bảng đếm hai thứ khác nhau và không có khoá ngoại nối nhau, nên
  // gộp chung một nhãn là tạo ra đúng nhầm lẫn mà m39 sinh ra để sửa.
  if (it?.available) {
    tiles.push({ icon: <ClipboardList size={20} />, tone: 'info', label: 'Tổng phiếu nhận', value: n(it.total), to: '/sample-flow' });
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Quá hạn trả kết quả', value: n(it.overdue), to: '/sample-flow' });
    tiles.push({ icon: <CheckCircle2 size={20} />, tone: 'success', label: 'Đã trả kết quả', value: n(it.by_status?.completed), to: '/sample-flow' });
  }
  if (s?.available && n(s.total) > 0) {
    tiles.push({ icon: <ClipboardList size={20} />, tone: 'info', label: 'Mẫu M1 (module cũ)', value: n(s.total), to: '/samples' });
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Mẫu M1 quá hạn', value: n(s.overdue), to: '/samples?status=overdue' });
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
                { label: 'Phiếu quá hạn trả kết quả', value: n(it?.overdue), tone: 'overdue', to: '/sample-flow' },
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
