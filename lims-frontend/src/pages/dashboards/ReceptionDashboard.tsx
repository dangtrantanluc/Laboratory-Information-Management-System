import { ClipboardList, Inbox, Clock, AlertTriangle, Users } from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import * as reportingApi from '@/api/reporting';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec } from './DashKit';
import { SamplesOverTimeCard } from './DashCharts';

const n = (v: any) => v ?? 0;

/** Dashboard Phòng nhận mẫu — luồng mẫu vào: nhận → chuyển lab, không để tồn đọng. */
export function ReceptionDashboard() {
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const chartsQ = useAsync(() => reportingApi.getDashboardCharts(), []);
  const data = dashQ.data?.data as any;
  const charts = chartsQ.data?.data as any;
  // m39 — đếm PHIẾU NHẬN MẪU và LƯỢT CHUYỂN, tức là đúng hai bảng mà quầy ghi vào.
  // Trước đây các ô này lấy số từ `data.samples` (bảng của module M1) nhưng lại bấm
  // sang /sample-flow đọc `sample_intakes` — con số và màn hình đích khác nguồn.
  const it = data?.intakes;
  const dp = data?.dispatches;

  const tiles: KpiSpec[] = [];
  if (it?.available) {
    tiles.push({ icon: <ClipboardList size={20} />, tone: 'info', label: 'Tổng phiếu nhận', value: n(it.total), to: '/sample-flow' });
    tiles.push({ icon: <Inbox size={20} />, tone: 'pending', label: 'Chờ chuyển lab', value: n(it.awaiting_dispatch), to: '/sample-flow' });
  }
  if (dp?.available) {
    tiles.push({ icon: <Clock size={20} />, tone: 'warning', label: 'Đang xử lý ở lab', value: n(dp.in_progress), to: '/sample-flow' });
  }
  if (it?.available) {
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Quá hạn trả kết quả', value: n(it.overdue), to: '/sample-flow' });
  }

  return (
    <DashLayout
      subtitle="Luồng nhận & chuyển mẫu — không để mẫu tồn đọng"
      onRefresh={() => { dashQ.reload(); chartsQ.reload(); }}
      loading={dashQ.loading || chartsQ.loading}
    >
      <QuickActions
        actions={[
          { icon: <Inbox size={16} />, label: 'Nhận & chuyển mẫu', to: '/sample-flow' },
          { icon: <Users size={16} />, label: 'Khách hàng', to: '/customers' },
        ]}
      />

      {dashQ.loading ? (
        <Card><CardBody><LoadingState /></CardBody></Card>
      ) : (
        <>
          <KpiGrid items={tiles} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
            <AlertList
              title="Hàng đợi tiếp nhận"
              rows={[
                { label: 'Phiếu chờ chuyển lab', value: n(it?.awaiting_dispatch), tone: 'pending', to: '/sample-flow' },
                { label: 'Lab chưa tiếp nhận', value: n(dp?.waiting), tone: 'warning', to: '/sample-flow' },
                { label: 'Đang xử lý ở lab', value: n(dp?.in_progress), tone: 'info', to: '/sample-flow' },
                { label: 'Quá hạn trả kết quả', value: n(it?.overdue), tone: 'overdue', to: '/sample-flow' },
              ]}
            />
            <SamplesOverTimeCard charts={charts} loading={chartsQ.loading} title="Mẫu nhận theo kỳ" subtitle="Thấy đỉnh tải để bố trí người" />
          </div>
        </>
      )}
    </DashLayout>
  );
}
