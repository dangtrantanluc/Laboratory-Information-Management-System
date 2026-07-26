import { useMemo } from 'react';
import { ShieldAlert, Layers, AlertOctagon, FolderArchive, Lightbulb, FileText, Bell } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { useChartHeight, useChartCompact } from '@/lib/useChart';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import { NC_STATUS_LABELS } from '@/types';
import * as reportingApi from '@/api/reporting';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec } from './DashKit';

const PIE_COLORS = ['#dc2626', '#d97706', '#2563eb', '#16a34a', '#6d28d9'];

/** Dashboard QLCL — chất lượng/tuân thủ VILAS: NC · CAPA · rủi ro · tài liệu. */
export function QmsDashboard() {
  const chartH = useChartHeight();
  const { isMobile } = useChartCompact();
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const chartsQ = useAsync(() => reportingApi.getDashboardCharts({ charts: 'nc_by_status' }), []);

  const data = dashQ.data?.data as any;
  const q = data?.qms;
  const doc = data?.documents;
  const notif = data?.notifications;

  const ncPie = useMemo(() => {
    const pts = (chartsQ.data?.data as any)?.nc_by_status?.data ?? [];
    return pts.map((p: any) => ({ name: (NC_STATUS_LABELS as Record<string, string>)[p.status] ?? p.status, value: p.count }));
  }, [chartsQ.data]);

  const tiles: KpiSpec[] = [];
  if (q?.available) {
    tiles.push({ icon: <ShieldAlert size={20} />, tone: 'overdue', label: 'Không phù hợp đang mở', value: q.nc_open ?? 0, to: '/nonconformities?status=open' });
    tiles.push({ icon: <Layers size={20} />, tone: 'pending', label: 'Đang xử lý CAPA', value: q.nc_open_capa ?? 0, to: '/nonconformities?status=in_capa' });
    tiles.push({ icon: <AlertOctagon size={20} />, tone: 'overdue', label: 'Rủi ro mức cao', value: q.risk_open_high ?? 0, to: '/risks?band=high' });
    tiles.push({ icon: <FolderArchive size={20} />, tone: 'warning', label: 'Minh chứng chờ duyệt', value: q.evidence_pending ?? 0, to: '/documents/pending' });
    tiles.push({ icon: <Lightbulb size={20} />, tone: 'info', label: 'Cải tiến đang thực hiện', value: q.improvements_open ?? 0, to: '/improvements' });
  }
  if (doc?.available) tiles.push({ icon: <FileText size={20} />, tone: 'pending', label: 'Tài liệu chờ duyệt', value: doc.pending_review ?? 0, to: '/documents/pending' });
  if (notif?.available) tiles.push({ icon: <Bell size={20} />, tone: 'info', label: 'Thông báo chưa đọc', value: notif.unread ?? 0, to: '/notifications' });

  return (
    <DashLayout
      subtitle="Chất lượng · tuân thủ VILAS/ISO 17025 · kiểm soát tài liệu"
      onRefresh={() => {
        dashQ.reload();
        chartsQ.reload();
      }}
      loading={dashQ.loading || chartsQ.loading}
    >
      <QuickActions
        actions={[
          { icon: <ShieldAlert size={16} />, label: 'Không phù hợp', to: '/nonconformities' },
          { icon: <AlertOctagon size={16} />, label: 'Rủi ro', to: '/risks' },
          { icon: <Lightbulb size={16} />, label: 'Cải tiến', to: '/improvements' },
          { icon: <FileText size={16} />, label: 'Duyệt tài liệu', to: '/documents/pending' },
        ]}
      />

      {dashQ.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : (
        <>
          <KpiGrid items={tiles} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
            <Card>
              <CardHeader title="Không phù hợp theo trạng thái" subtitle="Phân bố NC theo trạng thái xử lý" />
              <CardBody>
                {chartsQ.loading ? (
                  <LoadingState />
                ) : ncPie.length === 0 ? (
                  <EmptyState title="Chưa có dữ liệu NC" />
                ) : (
                  <ResponsiveContainer width="100%" height={chartH}>
                    <PieChart>
                      <Pie data={ncPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={isMobile ? 68 : 95} label={isMobile ? false : (e: any) => `${e.name}: ${e.value}`} labelLine={false} fontSize={11}>
                        {ncPie.map((_: any, i: number) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardBody>
            </Card>

            <AlertList
              title="Cần bạn xử lý"
              rows={[
                { label: 'NC đang mở (chưa xử lý)', value: q?.nc_open ?? 0, tone: 'overdue', to: '/nonconformities?status=open' },
                { label: 'CAPA đang thực hiện', value: q?.nc_open_capa ?? 0, tone: 'pending', to: '/nonconformities?status=in_capa' },
                { label: 'Rủi ro mức cao chưa xử lý', value: q?.risk_open_high ?? 0, tone: 'overdue', to: '/risks?band=high' },
                { label: 'Minh chứng VILAS chờ duyệt', value: q?.evidence_pending ?? 0, tone: 'warning', to: '/documents/pending' },
                { label: 'Tài liệu chờ ban hành', value: doc?.pending_review ?? 0, tone: 'pending', to: '/documents/pending' },
              ]}
            />
          </div>
        </>
      )}
    </DashLayout>
  );
}
