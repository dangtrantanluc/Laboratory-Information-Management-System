import { useMemo, useState } from 'react';
import {
  BarChart3,
  FileSpreadsheet,
  Search,
  ClipboardList,
  FlaskConical,
  ShieldCheck,
  UserSquare2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { useChartHeight, useChartCompact } from '@/lib/useChart';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Select, Input } from '@/components/ui/Field';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { cn } from '@/lib/cn';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import {
  SAMPLE_STATUS_LABELS,
  MEASUREMENT_GROUP_LABELS,
  type SampleStatus,
  type DashboardMeta,
} from '@/types';
import {
  canViewCustomerReport,
  canViewSampleReport,
  canViewChemicalReport,
  canViewSystemAccess,
  canViewCost,
} from '@/lib/rbac';
import * as reportingApi from '@/api/reporting';
import * as usersApi from '@/api/users';
import { formatDateTime, formatMoney, formatNumber } from '@/lib/format';

type TabKey = 'samples' | 'chemicals' | 'customers' | 'system-access';

export function Reports() {
  const { user } = useAuth();
  const showSamples = canViewSampleReport(user);
  const showChem = canViewChemicalReport(user);
  const showR15 = canViewSystemAccess(user);
  const showCustomers = canViewCustomerReport(user);

  const tabs = useMemo(() => {
    const t: { key: TabKey; label: string; icon: React.ReactNode }[] = [];
    if (showSamples) t.push({ key: 'samples', label: 'Báo cáo mẫu', icon: <ClipboardList size={15} /> });
    if (showChem) t.push({ key: 'chemicals', label: 'Báo cáo hóa chất', icon: <FlaskConical size={15} /> });
    if (showCustomers) t.push({ key: 'customers', label: 'Khách hàng', icon: <UserSquare2 size={15} /> });
    if (showR15) t.push({ key: 'system-access', label: 'Truy cập hệ thống', icon: <ShieldCheck size={15} /> });
    return t;
  }, [showSamples, showChem, showCustomers, showR15]);

  const [tab, setTab] = useState<TabKey>(tabs[0]?.key ?? 'chemicals');

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Báo cáo & Thống kê"
        description="Tổng hợp số liệu theo thời gian, phòng ban — xuất Excel / PDF"
        icon={<BarChart3 size={20} />}
      />

      {tabs.length === 0 ? (
        <Card>
          <EmptyState title="Không có báo cáo khả dụng" description="Vai trò của bạn chưa được cấp báo cáo nào." />
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-1 border-b border-hairline">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors',
                  tab === t.key
                    ? 'border-blueberry text-blueberry'
                    : 'border-transparent text-subink hover:text-ink',
                )}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          {tab === 'samples' && showSamples && <SamplesReportTab />}
          {tab === 'chemicals' && showChem && <ChemicalsReportTab />}
          {tab === 'customers' && showCustomers && <CustomersReportTab />}
          {tab === 'system-access' && showR15 && <SystemAccessTab />}
        </>
      )}
    </div>
  );
}

/** Bộ lọc thời gian + phòng dùng chung. */
function FilterBar({
  from,
  to,
  setFrom,
  setTo,
  departmentId,
  setDepartmentId,
  showDepartment,
  onApply,
  extra,
}: {
  from: string;
  to: string;
  setFrom: (v: string) => void;
  setTo: (v: string) => void;
  departmentId?: string;
  setDepartmentId?: (v: string) => void;
  showDepartment?: boolean;
  onApply: () => void;
  extra?: React.ReactNode;
}) {
  const { user } = useAuth();
  const isStaff = user?.role === 'staff';
  const { data: depts } = useAsync(
    () => (showDepartment && !isStaff ? usersApi.listDepartments() : Promise.resolve(null)),
    [showDepartment, isStaff],
  );

  return (
    <Card>
      <CardBody className="pt-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-5">
          <Field label="Từ ngày">
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="Đến ngày">
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          {showDepartment && setDepartmentId && (
            <Field label="Phòng ban">
              <Select
                value={departmentId}
                onChange={(e) => setDepartmentId(e.target.value)}
                disabled={isStaff}
              >
                <option value="">{isStaff ? 'Phòng của bạn' : '— Toàn hệ thống —'}</option>
                {(depts?.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          {extra}
          <div className="flex items-end">
            <Button onClick={onApply} className="w-full">
              <Search size={16} /> Xem báo cáo
            </Button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function MetaLine({ meta }: { meta?: DashboardMeta }) {
  if (!meta?.generated_at) return null;
  return (
    <p className="text-xs text-subink">
      Cập nhật lúc {formatDateTime(meta.generated_at)}
      {meta.cached ? ' · từ bộ nhớ đệm' : ''}
    </p>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <CardBody className="pt-5">
        <p className="text-xs text-subink">{label}</p>
        <p className="text-2xl font-bold text-ink">{value}</p>
      </CardBody>
    </Card>
  );
}

// ── Tab: Báo cáo mẫu ────────────────────────────────────────────
const SAMPLE_STATUS_ORDER: SampleStatus[] = [
  'received',
  'assigned',
  'testing',
  'overdue',
  'done',
  'returned',
];

function SamplesReportTab() {
  const chartH = useChartHeight();
  const { xAxis, yAxis } = useChartCompact();
  const toast = useToast();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [breakdown, setBreakdown] = useState<'status' | 'time' | 'department'>('status');
  const [applied, setApplied] = useState<reportingApi.SamplesReportFilters | null>(null);
  const [exporting, setExporting] = useState(false);

  function build(): reportingApi.SamplesReportFilters | null {
    if (from && to && from >= to) {
      toast.error('Từ ngày phải trước đến ngày');
      return null;
    }
    return {
      from: from || undefined,
      to: to || undefined,
      department_id: departmentId || undefined,
      breakdown,
    };
  }
  function run() {
    const f = build();
    if (f) setApplied(f);
  }
  async function exportXlsx() {
    const f = build();
    if (!f) return;
    setExporting(true);
    try {
      await reportingApi.exportReportXlsx('samples', { ...f });
      toast.success('Đã tải file Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const q = useAsync(
    () => (applied ? reportingApi.getSamplesReport(applied) : Promise.resolve(null)),
    [applied],
  );
  const d = q.data?.data;

  const barData = useMemo(() => {
    if (!d) return [];
    if (d.breakdown_by === 'status') {
      return SAMPLE_STATUS_ORDER.map((s) => ({
        name: SAMPLE_STATUS_LABELS[s],
        value: d.by_status?.[s] ?? 0,
      }));
    }
    if (d.breakdown_by === 'time') {
      return (d.by_time ?? []).map((p) => ({ name: p.period, value: p.count }));
    }
    return (d.by_department ?? []).map((p) => ({ name: p.department_name, value: p.count }));
  }, [d]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="secondary" onClick={exportXlsx} loading={exporting}>
          <FileSpreadsheet size={16} /> Xuất Excel
        </Button>
      </div>
      <FilterBar
        from={from}
        to={to}
        setFrom={setFrom}
        setTo={setTo}
        departmentId={departmentId}
        setDepartmentId={setDepartmentId}
        showDepartment
        onApply={run}
        extra={
          <Field label="Phân rã theo">
            <Select value={breakdown} onChange={(e) => setBreakdown(e.target.value as typeof breakdown)}>
              <option value="status">Trạng thái</option>
              <option value="time">Thời gian</option>
              <option value="department">Phòng ban</option>
            </Select>
          </Field>
        }
      />

      {q.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : q.error ? (
        <Card>
          <EmptyState title="Không tải được báo cáo" description={describeError(q.error).title} />
        </Card>
      ) : !d ? (
        <Card>
          <EmptyState title="Chọn kỳ và bấm Xem báo cáo" description="Kết quả thống kê số mẫu sẽ hiển thị tại đây." />
        </Card>
      ) : (
        <>
          <MetaLine meta={q.data?.meta} />
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard label="Tổng số mẫu" value={formatNumber(d.total)} />
            <StatCard label="Đang thực nghiệm" value={d.by_status?.testing ?? 0} />
            <StatCard label="Quá hạn" value={d.by_status?.overdue ?? 0} />
            <StatCard label="Đã chốt" value={d.by_status?.done ?? 0} />
          </div>
          <Card>
            <CardHeader
              title={`Phân rã theo ${breakdown === 'status' ? 'trạng thái' : breakdown === 'time' ? 'thời gian' : 'phòng ban'}`}
            />
            <CardBody>
              {barData.length === 0 || barData.every((b) => b.value === 0) ? (
                <EmptyState title="Không có dữ liệu trong kỳ đã chọn" />
              ) : (
                <ResponsiveContainer width="100%" height={chartH}>
                  <BarChart data={barData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e8f2ec" vertical={false} />
                    <XAxis dataKey="name" {...xAxis} tick={{ ...xAxis.tick, fill: '#6b7a72' }} />
                    <YAxis allowDecimals={false} {...yAxis} tick={{ ...yAxis.tick, fill: '#6b7a72' }} />
                    <Tooltip />
                    <Bar dataKey="value" name="Số mẫu" fill="#0d8256" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Tab: Báo cáo hóa chất ───────────────────────────────────────
function ChemicalsReportTab() {
  const { user } = useAuth();
  const toast = useToast();
  const showCost = canViewCost(user);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [metric, setMetric] = useState<'consumption' | 'stock'>('consumption');
  const [applied, setApplied] = useState<reportingApi.ChemicalsReportFilters | null>(null);
  const [exporting, setExporting] = useState(false);

  function build(): reportingApi.ChemicalsReportFilters | null {
    if (from && to && from >= to) {
      toast.error('Từ ngày phải trước đến ngày');
      return null;
    }
    return {
      from: from || undefined,
      to: to || undefined,
      department_id: departmentId || undefined,
      metric,
    };
  }
  function run() {
    const f = build();
    if (f) setApplied(f);
  }
  async function exportXlsx() {
    const f = build();
    if (!f) return;
    setExporting(true);
    try {
      await reportingApi.exportReportXlsx('chemicals', { ...f });
      toast.success('Đã tải file Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const q = useAsync(
    () => (applied ? reportingApi.getChemicalsReport(applied) : Promise.resolve(null)),
    [applied],
  );
  const d = q.data?.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="secondary" onClick={exportXlsx} loading={exporting}>
          <FileSpreadsheet size={16} /> Xuất Excel
        </Button>
      </div>
      <FilterBar
        from={from}
        to={to}
        setFrom={setFrom}
        setTo={setTo}
        departmentId={departmentId}
        setDepartmentId={setDepartmentId}
        showDepartment
        onApply={run}
        extra={
          <Field label="Chỉ tiêu">
            <Select value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>
              <option value="consumption">Tiêu hao</option>
              <option value="stock">Tồn hiện tại</option>
            </Select>
          </Field>
        }
      />

      {q.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : q.error ? (
        <Card>
          <EmptyState title="Không tải được báo cáo" description={describeError(q.error).title} />
        </Card>
      ) : !d ? (
        <Card>
          <EmptyState
            title="Chọn kỳ và bấm Xem báo cáo"
            description="Thống kê tiêu hao / tồn hóa chất theo nhóm đo sẽ hiển thị tại đây."
          />
        </Card>
      ) : (
        <>
          <MetaLine meta={q.data?.meta} />
          {showCost && d.total_cost !== undefined && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <StatCard label="Tổng chi phí (VND)" value={formatNumber(d.total_cost)} />
            </div>
          )}
          <Card>
            <CardHeader
              title="Theo nhóm đo lường"
              subtitle="Không cộng gộp khác đơn vị (khối lượng / thể tích / đếm tách riêng)"
            />
            <CardBody className="pt-0">
              {d.by_measurement_group.length === 0 ? (
                <EmptyState title="Không có dữ liệu trong kỳ đã chọn" />
              ) : (
                <div className="overflow-x-auto scrollbar-thin">
                  <table className="w-full min-w-[560px] text-sm table-sticky-1">
                    <thead>
                      <tr className="border-b border-hairline text-left text-xs text-subink">
                        <th className="py-2 pr-4 font-medium">Nhóm đo</th>
                        <th className="py-2 pr-4 font-medium">Đơn vị</th>
                        <th className="py-2 pr-4 text-right font-medium">
                          {metric === 'stock' ? 'Tồn' : 'Tiêu hao'}
                        </th>
                        {showCost && <th className="py-2 text-right font-medium">Chi phí (VND)</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {d.by_measurement_group.map((g) => (
                        <tr key={g.measurement_group} className="border-b border-hairline/60 last:border-0">
                          <td className="py-2.5 pr-4 font-medium text-ink">
                            {MEASUREMENT_GROUP_LABELS[g.measurement_group] ?? g.measurement_group}
                          </td>
                          <td className="py-2.5 pr-4 text-subink">{g.base_unit}</td>
                          <td className="py-2.5 pr-4 text-right font-semibold text-ink">
                            {formatNumber(g.total_qty)} {g.base_unit}
                          </td>
                          {showCost && (
                            <td className="py-2.5 text-right text-ink">
                              {g.consumption_cost !== undefined ? formatNumber(g.consumption_cost) : '—'}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Tab: Thống kê truy cập hệ thống (R15) ───────────────────────
function SystemAccessTab() {
  const toast = useToast();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [applied, setApplied] = useState<reportingApi.SystemAccessFilters | null>(null);
  const [exporting, setExporting] = useState(false);

  function build(): reportingApi.SystemAccessFilters | null {
    if (from && to && from >= to) {
      toast.error('Từ ngày phải trước đến ngày');
      return null;
    }
    return { from: from || undefined, to: to || undefined, top_n: 10 };
  }
  function run() {
    const f = build();
    if (f) setApplied(f);
  }
  async function exportXlsx() {
    const f = build();
    if (!f) return;
    setExporting(true);
    try {
      await reportingApi.exportReportXlsx('system-access', { from: f.from, to: f.to });
      toast.success('Đã tải file Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const q = useAsync(
    () => (applied ? reportingApi.getSystemAccess(applied) : Promise.resolve(null)),
    [applied],
  );
  const d = q.data?.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="secondary" onClick={exportXlsx} loading={exporting}>
          <FileSpreadsheet size={16} /> Xuất Excel
        </Button>
      </div>
      <FilterBar from={from} to={to} setFrom={setFrom} setTo={setTo} onApply={run} />

      {q.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : q.error ? (
        <Card>
          <EmptyState title="Không tải được báo cáo" description={describeError(q.error).title} />
        </Card>
      ) : !d ? (
        <Card>
          <EmptyState
            title="Chọn kỳ và bấm Xem báo cáo"
            description="Lượt truy cập / tải / chỉnh sửa toàn hệ thống + top người dùng sẽ hiển thị tại đây."
          />
        </Card>
      ) : (
        <>
          <MetaLine meta={q.data?.meta} />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard label="Lượt truy cập" value={formatNumber(d.totals.access_count)} />
            <StatCard label="Lượt tải tài liệu" value={formatNumber(d.totals.download_count)} />
            <StatCard label="Lượt chỉnh sửa" value={formatNumber(d.totals.edit_count)} />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <TopUsersCard title="Truy cập nhiều nhất" users={d.top_users.access} />
            <TopUsersCard title="Tải nhiều nhất" users={d.top_users.download} />
            <TopUsersCard title="Chỉnh sửa nhiều nhất" users={d.top_users.edit} />
          </div>
        </>
      )}
    </div>
  );
}

function TopUsersCard({
  title,
  users,
}: {
  title: string;
  users: { user_id: string; user_name: string; count: number }[];
}) {
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody className="pt-0">
        {users.length === 0 ? (
          <EmptyState title="Không có dữ liệu" />
        ) : (
          <ul className="flex flex-col divide-y divide-hairline">
            {users.map((u, i) => (
              <li key={u.user_id} className="flex items-center justify-between gap-2 py-2.5">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-plate text-xs font-semibold text-stem">
                    {i + 1}
                  </span>
                  <span className="truncate text-sm text-ink">{u.user_name}</span>
                </span>
                <span className="shrink-0 text-sm font-semibold text-ink">{formatNumber(u.count)}</span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

/**
 * Báo cáo tổng hợp khách hàng (m50) — phục vụ Văn phòng làm báo cáo tháng.
 *
 * "Khách mới" và "khách hoạt động" hiển thị TÁCH NHAU và không cộng vào nhau: một
 * khách tạo từ năm ngoái mà tháng này gửi mẫu thì hoạt động chứ không mới. Đặt cạnh
 * nhau mà không nói rõ là mời người đọc cộng nhầm.
 */
function CustomersReportTab() {
  const chartH = useChartHeight();
  const { xAxis, yAxis } = useChartCompact();
  const toast = useToast();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [applied, setApplied] = useState<reportingApi.ReportFilters | null>({});

  function run() {
    if (from && to && from >= to) {
      toast.error('Từ ngày phải trước đến ngày');
      return;
    }
    setApplied({ from: from || undefined, to: to || undefined });
  }

  const q = useAsync(
    () => (applied ? reportingApi.getCustomersReport(applied) : Promise.resolve(null)),
    [applied],
  );
  const d = q.data?.data;

  return (
    <div className="flex flex-col gap-4">
      <FilterBar from={from} to={to} setFrom={setFrom} setTo={setTo} onApply={run} />

      {/* Dạng ba ngôi như các tab khác: `q.error` có kiểu `unknown`, nên `q.error && <JSX>`
          trả về `unknown` và TypeScript từ chối coi đó là nội dung render được. */}
      {q.loading ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : q.error ? (
        <Card>
          <EmptyState title="Không tải được báo cáo" description={describeError(q.error).title} />
        </Card>
      ) : !d ? (
        <Card>
          <EmptyState
            title="Chưa có số liệu"
            description="Chọn kỳ rồi bấm Xem báo cáo."
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatCard label="Khách mới trong kỳ" value={formatNumber(d.summary.new_customers)} />
            <StatCard label="Khách có phát sinh" value={formatNumber(d.summary.active_customers)} />
            <StatCard label="Tổng khách trong sổ" value={formatNumber(d.summary.total_customers)} />
            <StatCard label="Phiếu nhận mẫu" value={formatNumber(d.summary.intakes)} />
            <StatCard label="Đã thu" value={formatMoney(d.summary.paid_total, 'VND')} />
          </div>

          <Card>
            <CardHeader
              title="Diễn biến theo kỳ"
              subtitle="Khách mới và khách có phát sinh là hai con số khác nhau — không cộng vào nhau."
            />
            <CardBody>
              {d.series.length === 0 ? (
                <EmptyState title="Chưa có số liệu" description="Kỳ đã chọn không có hoạt động nào." />
              ) : (
                <ResponsiveContainer width="100%" height={chartH}>
                  <BarChart data={d.series}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="period" {...xAxis} />
                    <YAxis allowDecimals={false} {...yAxis} />
                    <Tooltip />
                    <Bar dataKey="new_customers" name="Khách mới" fill="#2a78d6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="active_customers" name="Khách có phát sinh" fill="#eb6834" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="intakes" name="Phiếu nhận mẫu" fill="#1baf7a" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Khách hàng nhiều phiếu nhất"
              subtitle="Tối đa 10 khách, xếp theo số phiếu nhận mẫu trong kỳ."
            />
            <CardBody>
              {d.top_customers.length === 0 ? (
                <EmptyState title="Chưa có khách hàng nào phát sinh trong kỳ" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-hairline bg-plate">
                        <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-stem">
                          Khách hàng
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-stem">
                          Số phiếu
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-stem">
                          Giá trị báo giá
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-stem">
                          Đã thu
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      {d.top_customers.map((c) => (
                        <tr key={`${c.customer_id ?? c.name}`}>
                          <td className="px-3 py-2">
                            <span className="font-medium text-ink">{c.name}</span>
                            {/* Khách vãng lai không có trong sổ — nói rõ để người làm báo
                                cáo biết con số này không tra ngược được sang master data. */}
                            {c.is_walk_in && (
                              <span className="ml-2 text-xs text-subink">(khách vãng lai)</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right">{formatNumber(c.intakes)}</td>
                          <td className="px-3 py-2 text-right">{formatMoney(c.quoted_total, 'VND')}</td>
                          <td className="px-3 py-2 text-right">{formatMoney(c.paid_total, 'VND')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>

          <MetaLine meta={q.data?.meta} />
        </>
      )}
    </div>
  );
}
