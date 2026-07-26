import { ClipboardList, Clock, AlertTriangle, CheckCircle2, CalendarClock, FileText, Bell, FlaskConical } from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/States';
import { useAsync } from '@/lib/useAsync';
import * as reportingApi from '@/api/reporting';
import { DashLayout, KpiGrid, QuickActions, AlertList, type KpiSpec } from './DashKit';

const n = (v: any) => v ?? 0;

/** Dashboard KTV — cá nhân/vận hành: mẫu trong phòng, việc cần làm, nhắc nộp báo cáo. */
export function StaffDashboard() {
  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const data = dashQ.data?.data as any;
  const s = data?.samples;
  const c = data?.chemicals;
  const doc = data?.documents;
  const notif = data?.notifications;

  const tiles: KpiSpec[] = [];
  if (s?.available) {
    tiles.push({ icon: <ClipboardList size={20} />, tone: 'info', label: 'Mẫu trong phòng', value: n(s.total), to: '/samples' });
    tiles.push({ icon: <Clock size={20} />, tone: 'pending', label: 'Đang thực nghiệm', value: n(s.by_status?.testing), to: '/samples' });
    tiles.push({ icon: <AlertTriangle size={20} />, tone: 'overdue', label: 'Quá hạn', value: n(s.overdue), to: '/samples' });
    tiles.push({ icon: <CheckCircle2 size={20} />, tone: 'success', label: 'Đã chốt', value: n(s.by_status?.done) });
  }
  if (c?.available) tiles.push({ icon: <FlaskConical size={20} />, tone: 'warning', label: 'Hóa chất sắp hết hạn', value: n(c.expiring_soon), to: '/chemicals' });
  if (doc?.available) tiles.push({ icon: <FileText size={20} />, tone: 'pending', label: 'Tài liệu chờ duyệt', value: n(doc.pending_review), to: '/documents/pending' });
  if (notif?.available) tiles.push({ icon: <Bell size={20} />, tone: 'info', label: 'Thông báo chưa đọc', value: n(notif.unread), to: '/notifications' });

  return (
    <DashLayout subtitle="Công việc của bạn hôm nay" onRefresh={dashQ.reload} loading={dashQ.loading}>
      <QuickActions
        actions={[
          { icon: <ClipboardList size={16} />, label: 'Nhập kết quả', to: '/samples' },
          { icon: <CalendarClock size={16} />, label: 'Nộp báo cáo hoạt động', to: '/activity-reports/new' },
          { icon: <FileText size={16} />, label: 'Tài liệu', to: '/documents' },
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
            <AlertList
              title="Việc cần làm"
              rows={[
                { label: 'Mẫu chờ nhập kết quả (đã phân công)', value: n(s?.by_status?.assigned), tone: 'pending', to: '/samples?status=assigned' },
                { label: 'Mẫu đang thực nghiệm', value: n(s?.by_status?.testing), tone: 'pending', to: '/samples?status=testing' },
                { label: 'Mẫu quá hạn', value: n(s?.overdue), tone: 'overdue', to: '/samples?status=overdue' },
                { label: 'Thông báo chưa đọc', value: n(notif?.unread), tone: 'info', to: '/notifications' },
              ]}
            />
            <AlertList
              title="Nhắc việc"
              rows={[
                { label: 'Hóa chất sắp hết hạn (phòng)', value: n(c?.expiring_soon), tone: 'warning', to: '/chemicals' },
                { label: 'Hóa chất tồn thấp (phòng)', value: n(c?.low_stock), tone: 'overdue', to: '/chemicals' },
                { label: 'Tài liệu chờ duyệt', value: n(doc?.pending_review), tone: 'pending', to: '/documents/pending' },
              ]}
            />
          </div>
        </>
      )}
    </DashLayout>
  );
}
