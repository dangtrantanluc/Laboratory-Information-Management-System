import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardList,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Wrench,
  FileText,
  Bell,
  CalendarClock,
  TrendingDown,
  Wallet,
  RefreshCw,
  FileDown,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { SAMPLE_STATUS_LABELS, MEASUREMENT_GROUP_LABELS } from '@/types';
import { canViewCost } from '@/lib/rbac';
import { describeError } from '@/lib/errors';
import * as reportingApi from '@/api/reporting';
import { formatDateTime, formatNumber } from '@/lib/format';

const PIE_COLORS = ['#5c6b8a', '#a29f76', '#3b82f6', '#ef4444', '#22c55e', '#8b5cf6'];

export function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const showCost = canViewCost(user);
  const [exporting, setExporting] = useState(false);

  const dashQ = useAsync(() => reportingApi.getDashboard(), []);
  const chartsQ = useAsync(() => reportingApi.getDashboardCharts(), []);

  async function exportPdf() {
    setExporting(true);
    try {
      await reportingApi.exportReportPdf('dashboard');
      toast.success('Đã xuất PDF tổng quan');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const data = dashQ.data?.data;
  const meta = dashQ.data?.meta;
  const charts = chartsQ.data?.data;

  const pieData = useMemo(() => {
    const pts = charts?.samples_by_status?.data ?? [];
    return pts.map((p) => ({
      name: SAMPLE_STATUS_LABELS[p.status] ?? p.status,
      value: p.count,
    }));
  }, [charts]);

  const lineData = useMemo(
    () => (charts?.samples_over_time?.data ?? []).map((p) => ({ name: p.period, value: p.count })),
    [charts],
  );

  // Tiêu hao hóa chất: tách theo nhóm đo (KHÔNG cộng g + mL). Gộp theo period thành cột.
  const barGroups = charts?.chemical_consumption?.by_measurement_group ?? [];
  const barData = useMemo(() => {
    const byPeriod = new Map<string, Record<string, number | string>>();
    for (const g of barGroups) {
      const key = `${MEASUREMENT_GROUP_LABELS[g.measurement_group] ?? g.measurement_group} (${g.base_unit})`;
      for (const pt of g.data) {
        const row = byPeriod.get(pt.period) ?? { name: pt.period };
        row[key] = pt.qty;
        byPeriod.set(pt.period, row);
      }
    }
    return Array.from(byPeriod.values());
  }, [barGroups]);
  const barKeys = barGroups.map(
    (g) => `${MEASUREMENT_GROUP_LABELS[g.measurement_group] ?? g.measurement_group} (${g.base_unit})`,
  );

  const samples = data?.samples;
  const chemicals = data?.chemicals;
  const equipments = data?.equipments;
  const hr = data?.hr;
  const documents = data?.documents;
  const notifications = data?.notifications;

  const hasSamplesChart = charts ? 'samples_by_status' in charts : false;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`Xin chào, ${user?.full_name ?? ''}`}
        description="Tổng quan hoạt động phòng thí nghiệm"
        icon={<LayoutDashboard size={20} />}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                dashQ.reload();
                chartsQ.reload();
              }}
              loading={dashQ.loading || chartsQ.loading}
            >
              <RefreshCw size={15} /> Làm mới
            </Button>
            <Button size="sm" onClick={exportPdf} loading={exporting}>
              <FileDown size={15} /> Xuất PDF
            </Button>
          </div>
        }
      />

      {meta?.generated_at && (
        <p className="-mt-3 text-xs text-subink">
          Cập nhật lúc {formatDateTime(meta.generated_at)}
          {meta.cached ? ' · từ bộ nhớ đệm' : ''}
        </p>
      )}

      {dashQ.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : !data ? (
        <Card>
          <CardBody>
            <EmptyState title="Không tải được tổng quan" description="Vui lòng thử lại sau." />
          </CardBody>
        </Card>
      ) : (
        <>
          {/* ── KPI cards (chỉ khối có trong response) ── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {samples?.available && (
              <>
                <KpiCard
                  icon={<ClipboardList size={20} />}
                  tone="info"
                  label="Tổng mẫu"
                  value={samples.total ?? 0}
                  onClick={() => navigate('/samples')}
                />
                <KpiCard
                  icon={<Clock size={20} />}
                  tone="pending"
                  label="Đang thực nghiệm"
                  value={samples.by_status?.testing ?? 0}
                />
                <KpiCard
                  icon={<AlertTriangle size={20} />}
                  tone="overdue"
                  label="Mẫu quá hạn"
                  value={samples.overdue ?? 0}
                  onClick={() => navigate('/samples')}
                />
                <KpiCard
                  icon={<CheckCircle2 size={20} />}
                  tone="success"
                  label="Đã chốt"
                  value={samples.by_status?.done ?? 0}
                />
              </>
            )}

            {chemicals?.available && (
              <>
                <KpiCard
                  icon={<CalendarClock size={20} />}
                  tone="warning"
                  label="Hóa chất sắp hết hạn"
                  value={chemicals.expiring_soon ?? 0}
                  onClick={() => navigate('/chemicals')}
                />
                <KpiCard
                  icon={<TrendingDown size={20} />}
                  tone="overdue"
                  label="Hóa chất tồn thấp"
                  value={chemicals.low_stock ?? 0}
                  onClick={() => navigate('/chemicals')}
                />
                {showCost && chemicals.consumption_cost_month !== undefined && (
                  <KpiCard
                    icon={<Wallet size={20} />}
                    tone="info"
                    label="Chi phí tiêu hao (tháng)"
                    value={formatNumber(chemicals.consumption_cost_month)}
                  />
                )}
              </>
            )}

            {equipments?.available && (
              <KpiCard
                icon={<Wrench size={20} />}
                tone="overdue"
                label="Thiết bị quá hạn hiệu chuẩn"
                value={equipments.calibration_overdue ?? 0}
                onClick={() => navigate('/equipment')}
              />
            )}

            {hr?.available && (
              <KpiCard
                icon={<CalendarClock size={20} />}
                tone="warning"
                label="Nâng lương / HĐ sắp tới hạn"
                value={(hr.salary_raise_due ?? 0) + (hr.contract_ending ?? 0)}
                onClick={() => navigate('/hr')}
              />
            )}

            {documents?.available && (
              <KpiCard
                icon={<FileText size={20} />}
                tone="pending"
                label="Tài liệu chờ duyệt"
                value={documents.pending_review ?? 0}
                onClick={() => navigate('/documents/pending')}
              />
            )}

            {notifications?.available && (
              <KpiCard
                icon={<Bell size={20} />}
                tone="info"
                label="Thông báo chưa đọc"
                value={notifications.unread ?? 0}
                onClick={() => navigate('/notifications')}
              />
            )}
          </div>

          {/* ── Biểu đồ ── */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {hasSamplesChart && charts?.samples_by_status?.available && (
              <Card>
                <CardHeader title="Mẫu theo trạng thái" subtitle="Phân bố trạng thái mẫu" />
                <CardBody>
                  {chartsQ.loading ? (
                    <LoadingState />
                  ) : pieData.length === 0 ? (
                    <EmptyState title="Chưa có dữ liệu mẫu" />
                  ) : (
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={pieData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={95}
                          label={(e) => `${e.name}: ${e.value}`}
                          labelLine={false}
                          fontSize={11}
                        >
                          {pieData.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </CardBody>
              </Card>
            )}

            {charts?.samples_over_time?.available && (
              <Card>
                <CardHeader title="Mẫu theo thời gian" subtitle="Số mẫu tiếp nhận theo kỳ" />
                <CardBody>
                  {chartsQ.loading ? (
                    <LoadingState />
                  ) : lineData.length === 0 ? (
                    <EmptyState title="Chưa có dữ liệu" />
                  ) : (
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={lineData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#7b8499' }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#7b8499' }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="value" stroke="#2f3a55" strokeWidth={2} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </CardBody>
              </Card>
            )}

            {charts?.chemical_consumption?.available && (
              <Card className={hasSamplesChart ? 'lg:col-span-2' : ''}>
                <CardHeader
                  title="Tiêu hao hóa chất theo tháng"
                  subtitle="Tách theo nhóm đo lường (không cộng gộp khác đơn vị)"
                />
                <CardBody>
                  {chartsQ.loading ? (
                    <LoadingState />
                  ) : barData.length === 0 ? (
                    <EmptyState title="Chưa có dữ liệu tiêu hao" />
                  ) : (
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={barData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#7b8499' }} />
                        <YAxis tick={{ fontSize: 11, fill: '#7b8499' }} />
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        {barKeys.map((k, i) => (
                          <Bar key={k} dataKey={k} fill={PIE_COLORS[i % PIE_COLORS.length]} radius={[4, 4, 0, 0]} />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </CardBody>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  tone,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  tone: 'info' | 'pending' | 'overdue' | 'success' | 'warning';
  onClick?: () => void;
}) {
  const tones: Record<string, string> = {
    info: 'bg-berry/10 text-berry',
    pending: 'bg-pending/10 text-pending',
    overdue: 'bg-overdue/10 text-overdue',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-[#b45309]',
  };
  return (
    <Card className={onClick ? 'cursor-pointer transition-shadow hover:shadow-pop' : ''}>
      <CardBody className="flex items-center gap-4 pt-5" >
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${tones[tone]}`}>{icon}</div>
        <div onClick={onClick} className="min-w-0">
          <p className="text-2xl font-bold text-ink">{value}</p>
          <p className="text-xs text-subink">{label}</p>
        </div>
      </CardBody>
    </Card>
  );
}
