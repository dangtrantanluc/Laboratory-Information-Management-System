import { Inbox, Clock, AlertTriangle, CheckCircle2, Wrench, FlaskConical, TrendingDown, FileText, ClipboardList } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import * as reportingApi from '@/api/reporting';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec } from './DashKit';
import { SamplesByStatusCard, SamplesOverTimeCard } from './DashCharts';

const n = (v: any) => v ?? 0;

/** Dashboard Trưởng phòng lab — điều phối người/việc/nguồn lực trong phòng. */
export function LabManagerDashboard() {
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const chartsQ = useAsync(() => reportingApi.getDashboardCharts(), []);
  const workloadQ = useAsync(() => reportingApi.getLabWorkload(), []);
  const data = dashQ.data?.data as any;
  const charts = chartsQ.data?.data as any;
  const workload = (workloadQ.data?.data?.items ?? []).map((w) => ({ name: w.user_name, value: w.count }));
  const s = data?.samples;
  const c = data?.chemicals;
  const e = data?.equipments;
  const doc = data?.documents;

  const waitingAssign = n(s?.by_status?.received) + n(s?.by_status?.assigned);

  const tiles: KpiSpec[] = [];
  if (s?.available) {
    tiles.push({ icon: <Inbox size={20} />, tone: 'pending', label: 'Chờ phân công', value: waitingAssign, to: '/samples' });
    tiles.push({ icon: <Clock size={20} />, tone: 'info', label: 'Đang thực nghiệm', value: n(s.by_status?.testing), to: '/samples' });
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Mẫu quá hạn', value: n(s.overdue), to: '/samples' });
    tiles.push({ icon: <CheckCircle2 size={20} />, tone: 'success', label: 'Đã chốt', value: n(s.by_status?.done) });
  }
  if (e?.available) {
    tiles.push({ icon: <Wrench size={20} />, tone: 'overdue', label: 'Thiết bị quá hạn hiệu chuẩn', value: n(e.calibration_overdue), to: '/equipment' });
    tiles.push({ icon: <Wrench size={20} />, tone: 'warning', label: 'Sắp đến hạn hiệu chuẩn', value: n(e.calibration_due_soon), to: '/equipment' });
  }
  if (c?.available) tiles.push({ icon: <TrendingDown size={20} />, tone: 'overdue', label: 'Hóa chất tồn thấp', value: n(c.low_stock), to: '/chemicals' });
  if (doc?.available) tiles.push({ icon: <FileText size={20} />, tone: 'pending', label: 'Tài liệu chờ duyệt', value: n(doc.pending_review), to: '/documents/pending' });

  return (
    <DashLayout
      subtitle="Điều phối công việc & nguồn lực trong phòng"
      onRefresh={() => { dashQ.reload(); chartsQ.reload(); workloadQ.reload(); }}
      loading={dashQ.loading || chartsQ.loading || workloadQ.loading}
    >
      <QuickActions
        actions={[
          { icon: <ClipboardList size={16} />, label: 'Phân công mẫu', to: '/samples' },
          { icon: <Wrench size={16} />, label: 'Thiết bị & hiệu chuẩn', to: '/equipment' },
          { icon: <FlaskConical size={16} />, label: 'Hóa chất', to: '/chemicals' },
        ]}
      />

      {dashQ.loading ? (
        <Card><CardBody><LoadingState /></CardBody></Card>
      ) : (
        <>
          <KpiGrid items={tiles} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
            <SamplesByStatusCard charts={charts} loading={chartsQ.loading} />
            <AlertList
              title="Cần điều phối"
              rows={[
                { label: 'Mẫu chờ phân công KTV', value: waitingAssign, tone: 'pending', to: '/samples' },
                { label: 'Mẫu quá hạn', value: n(s?.overdue), tone: 'overdue', to: '/samples?status=overdue' },
                { label: 'Thiết bị quá hạn hiệu chuẩn', value: n(e?.calibration_overdue), tone: 'overdue', to: '/equipment' },
                { label: 'Hóa chất sắp hết hạn', value: n(c?.expiring_soon), tone: 'warning', to: '/chemicals' },
                { label: 'Hóa chất tồn thấp', value: n(c?.low_stock), tone: 'overdue', to: '/chemicals' },
              ]}
            />
            <SamplesOverTimeCard charts={charts} loading={chartsQ.loading} title="Throughput mẫu" subtitle="Số mẫu theo kỳ (nhìn tải công việc)" />
            <Card>
              <CardHeader title="Tải công việc theo KTV" subtitle="Số mẫu đang xử lý mỗi kỹ thuật viên (để cân việc)" />
              <CardBody>
                {workloadQ.loading ? (
                  <LoadingState />
                ) : workload.length === 0 ? (
                  <EmptyState title="Chưa có phân công đang xử lý" />
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={workload} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dceae3" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#6b7a72' }} />
                      <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: '#6b7a72' }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#0d8256" radius={[0, 4, 4, 0]} barSize={18} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </DashLayout>
  );
}
