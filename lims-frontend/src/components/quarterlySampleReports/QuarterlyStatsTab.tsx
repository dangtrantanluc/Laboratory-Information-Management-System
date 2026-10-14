/**
 * Tab "Báo cáo phân tích mẫu" ở trang Báo cáo & Thống kê — thống kê số mẫu các phòng lab
 * đã nộp theo quý (m54). Đây là tab Văn phòng xem; tab "Báo cáo mẫu" cũ (bảng phiếu mẫu
 * M1) vẫn ẩn với Văn phòng như trước.
 *
 * Backend trả ô phẳng phòng × quý × loại mẫu; tab cộng ra các góc nhìn: theo phòng, theo
 * loại mẫu, theo quý (khi xem cả năm) và bảng chéo phòng × loại mẫu. Mặc định chỉ tính
 * báo cáo đã chốt — cùng quy ước với file Excel xuất đi.
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, FileSpreadsheet } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Select } from '@/components/ui/Field';
import { EmptyState, LoadingState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { useChartCompact, useChartHeight } from '@/lib/useChart';
import { describeError } from '@/lib/errors';
import { formatNumber } from '@/lib/format';
import { TEST_MATRIX_LABELS, type TestMatrix } from '@/types';
import * as api from '@/api/quarterlySampleReports';

const BRAND = '#0d8256';
const INK_MUTED = '#6b7a72';
const GRID = '#e8f2ec';
const MATRIX_ORDER = Object.keys(TEST_MATRIX_LABELS) as TestMatrix[];

function shortName(name: string, max: number) {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

export function QuarterlyStatsTab() {
  const toast = useToast();
  const now = api.currentQuarter();
  const [year, setYear] = useState(now.year);
  const [quarter, setQuarter] = useState<number>(now.quarter); // 0 = cả năm
  const [dept, setDept] = useState('');
  const [includeUnlocked, setIncludeUnlocked] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data, loading, error } = useAsync(
    () =>
      api.getStats({
        year,
        quarter: quarter || undefined,
        department_id: dept || undefined,
        include_unlocked: includeUnlocked,
      }),
    [year, quarter, dept, includeUnlocked],
  );

  const view = useMemo(() => (data ? summarize(data, dept) : null), [data, dept]);
  const years = Array.from({ length: 4 }, (_, i) => now.year - i);
  const quarters = [1, 2, 3, 4].filter((q) => year < now.year || q <= now.quarter);
  const period = quarter ? api.periodLabel(year, quarter) : `Năm ${year}`;

  async function exportXlsx() {
    if (!quarter) return;
    setExporting(true);
    try {
      await api.exportQuarterlyReports(year, quarter, includeUnlocked);
      toast.success('Đã tải file Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Link
          to={`/quarterly-sample-reports?year=${year}&quarter=${quarter || now.quarter}`}
          className="inline-flex items-center gap-1.5 px-2 text-sm font-medium text-blueberry hover:underline"
        >
          <ExternalLink size={14} /> Mở danh sách chi tiết
        </Link>
        <Button
          variant="secondary"
          onClick={exportXlsx}
          loading={exporting}
          disabled={!quarter}
          title={quarter ? undefined : 'Chọn một quý để xuất file theo mẫu của Văn phòng'}
        >
          <FileSpreadsheet size={16} /> Xuất Excel
        </Button>
      </div>

      <Card>
        <CardBody className="grid grid-cols-1 gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Năm">
            <Select
              value={year}
              onChange={(e) => {
                const y = Number(e.target.value);
                setYear(y);
                if (y === now.year && quarter > now.quarter) setQuarter(now.quarter);
              }}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Quý">
            <Select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
              <option value={0}>Cả năm</option>
              {quarters.map((q) => (
                <option key={q} value={q}>
                  Quý {api.ROMAN[q]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Phòng nghiên cứu">
            <Select value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">— Tất cả phòng —</option>
              {(data?.departments ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
          <label className="flex items-center gap-2 self-end pb-2.5 text-sm text-subink">
            <input type="checkbox" checked={includeUnlocked} onChange={(e) => setIncludeUnlocked(e.target.checked)} />
            Gồm cả báo cáo chưa chốt
          </label>
        </CardBody>
      </Card>

      {error ? (
        <Card>
          <EmptyState title="Không tải được thống kê" description={describeError(error).title} />
        </Card>
      ) : !view || (loading && !data) ? (
        <Card>
          <CardBody>
            <LoadingState />
          </CardBody>
        </Card>
      ) : (
        <StatsBody view={view} period={period} wholeYear={!quarter} includeUnlocked={includeUnlocked} />
      )}
    </div>
  );
}

// ── Tổng hợp dữ liệu phẳng thành các góc nhìn ────────────────────
interface View {
  totalQty: number;
  totalItems: number;
  byDept: { id: string; name: string; qty: number; items: number }[];
  byMatrix: { matrix: TestMatrix; label: string; qty: number; items: number }[];
  byQuarter: { name: string; qty: number }[];
  pivotCols: { matrix: TestMatrix; label: string }[];
  pivotRows: { id: string; name: string; cells: Map<TestMatrix, number>; total: number }[];
  status: { locked: number; submitted: number; returned: number; draft: number; notStarted: number };
  top: { name: string; items: number }[];
}

function lastQuarterOf(year: number): number {
  const cur = api.currentQuarter();
  return year < cur.year ? 4 : year === cur.year ? cur.quarter : 0;
}

function summarize(d: api.QuarterlyStats, deptFilter: string): View {
  const depts = deptFilter ? d.departments.filter((x) => x.id === deptFilter) : d.departments;
  const deptQty = new Map<string, { qty: number; items: number; cells: Map<TestMatrix, number> }>();
  const matrixAgg = new Map<TestMatrix, { label: string; qty: number; items: number }>();
  const quarterQty = [0, 0, 0, 0];
  for (const c of d.cells) {
    const dq = deptQty.get(c.department_id) ?? { qty: 0, items: 0, cells: new Map() };
    dq.qty += c.quantity;
    dq.items += c.items;
    dq.cells.set(c.matrix, (dq.cells.get(c.matrix) ?? 0) + c.quantity);
    deptQty.set(c.department_id, dq);
    const m = matrixAgg.get(c.matrix) ?? { label: c.matrix_label, qty: 0, items: 0 };
    m.qty += c.quantity;
    m.items += c.items;
    matrixAgg.set(c.matrix, m);
    quarterQty[c.quarter - 1] += c.quantity;
  }
  const byDept = depts
    .map((x) => ({ id: x.id, name: x.name, qty: deptQty.get(x.id)?.qty ?? 0, items: deptQty.get(x.id)?.items ?? 0 }))
    .sort((a, b) => b.qty - a.qty || a.name.localeCompare(b.name, 'vi'));
  const byMatrix = MATRIX_ORDER.filter((m) => matrixAgg.has(m))
    .map((m) => ({ matrix: m, ...(matrixAgg.get(m) as { label: string; qty: number; items: number }) }))
    .sort((a, b) => b.qty - a.qty);
  const pivotCols = MATRIX_ORDER.filter((m) => matrixAgg.has(m)).map((m) => ({
    matrix: m,
    label: matrixAgg.get(m)?.label ?? TEST_MATRIX_LABELS[m],
  }));
  const pivotRows = depts.map((x) => {
    const dq = deptQty.get(x.id);
    return { id: x.id, name: x.name, cells: dq?.cells ?? new Map<TestMatrix, number>(), total: dq?.qty ?? 0 };
  });
  const count = (s: api.QuarterlyReportStatus) => d.reports.filter((r) => r.status === s).length;
  const expected = depts.length * (d.quarter ? 1 : quarterQty.length);
  return {
    totalQty: byDept.reduce((s, x) => s + x.qty, 0),
    totalItems: byDept.reduce((s, x) => s + x.items, 0),
    byDept,
    byMatrix,
    // Quý chưa tới không vẽ cột 0 — dễ đọc nhầm là "quý đó không có mẫu".
    byQuarter: quarterQty
      .map((qty, i) => ({ name: `Quý ${api.ROMAN[i + 1]}`, qty }))
      .slice(0, lastQuarterOf(d.year)),
    pivotCols,
    pivotRows,
    status: {
      locked: count('locked'),
      submitted: count('submitted'),
      returned: count('returned'),
      draft: count('draft'),
      notStarted: d.quarter ? Math.max(0, expected - d.reports.length) : 0,
    },
    top: d.top_criteria,
  };
}

// ── Nội dung ──────────────────────────────────────────────────────
function StatsBody({
  view,
  period,
  wholeYear,
  includeUnlocked,
}: {
  view: View;
  period: string;
  wholeYear: boolean;
  includeUnlocked: boolean;
}) {
  const s = view.status;
  const topMatrix = view.byMatrix[0];
  const labsWithData = view.byDept.filter((x) => x.qty > 0).length;

  return (
    <>
      <p className="text-sm text-subink">
        {period}: <b className="text-ink">{s.locked}</b> báo cáo đã chốt · {s.submitted} đã nộp chờ duyệt · {s.returned}{' '}
        bị trả lại · {s.draft} đang nhập
        {!wholeYear && <> · {s.notStarted} chưa bắt đầu</>}.{' '}
        {includeUnlocked ? 'Số liệu gồm cả báo cáo chưa chốt.' : 'Số liệu chỉ tính báo cáo đã chốt.'}
      </p>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <Stat label="Tổng số mẫu" value={formatNumber(view.totalQty)} />
        <Stat label="Số mã mẫu" value={formatNumber(view.totalItems)} />
        <Stat label="Phòng có mẫu" value={`${labsWithData}/${view.byDept.length}`} />
        <Stat label="Loại mẫu nhiều nhất" value={topMatrix ? topMatrix.label : '—'} small />
      </div>

      {view.totalQty === 0 ? (
        <Card>
          <EmptyState
            title="Chưa có số liệu trong kỳ này"
            description={
              includeUnlocked
                ? 'Các phòng lab chưa nhập mẫu nào.'
                : 'Chưa có báo cáo nào được chốt. Tích "Gồm cả báo cáo chưa chốt" để xem số liệu đang nhập.'
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <HBarCard
              title="Số mẫu theo phòng nghiên cứu"
              data={view.byDept.filter((x) => x.qty > 0).map((x) => ({ name: x.name, qty: x.qty }))}
            />
            <HBarCard title="Số mẫu theo loại mẫu" data={view.byMatrix.map((x) => ({ name: x.label, qty: x.qty }))} />
          </div>
          {wholeYear && <QuarterCard data={view.byQuarter} />}
          <PivotCard view={view} />
          <TopCriteriaCard top={view.top} />
        </>
      )}
    </>
  );
}

function Stat({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <Card>
      <CardBody className="pt-5">
        <p className="text-xs text-subink">{label}</p>
        <p className={small ? 'truncate text-base font-bold text-ink' : 'text-2xl font-bold text-ink'} title={value}>
          {value}
        </p>
      </CardBody>
    </Card>
  );
}

function QtyTooltip({ active, payload }: { active?: boolean; payload?: { payload: { name: string; qty: number } }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-ink">{p.name}</p>
      <p className="text-subink">
        Số mẫu: <b className="text-ink">{formatNumber(p.qty)}</b>
      </p>
    </div>
  );
}

/** Cột NGANG: tên phòng / loại mẫu dài, đặt trên trục dọc mới đọc được. Một chuỗi → một màu. */
function HBarCard({ title, data }: { title: string; data: { name: string; qty: number }[] }) {
  const { isMobile } = useChartCompact();
  const labelWidth = isMobile ? 110 : 220;
  const height = Math.max(120, data.length * 34 + 40);
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: INK_MUTED }} />
            <YAxis
              type="category"
              dataKey="name"
              width={labelWidth}
              tick={{ fontSize: 12, fill: INK_MUTED }}
              tickFormatter={(v: string) => shortName(v, isMobile ? 14 : 26)}
            />
            <Tooltip content={<QtyTooltip />} cursor={{ fill: '#0d825610' }} />
            <Bar
              dataKey="qty"
              fill={BRAND}
              barSize={16}
              radius={[0, 4, 4, 0]}
              label={{ position: 'right', fontSize: 12, fill: INK_MUTED }}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  );
}

function QuarterCard({ data }: { data: { name: string; qty: number }[] }) {
  const chartH = useChartHeight();
  const { xAxis, yAxis } = useChartCompact();
  return (
    <Card>
      <CardHeader title="Số mẫu theo quý" />
      <CardBody>
        <ResponsiveContainer width="100%" height={Math.min(chartH, 240)}>
          <BarChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="name" {...xAxis} tick={{ ...xAxis.tick, fill: INK_MUTED }} />
            <YAxis allowDecimals={false} {...yAxis} tick={{ ...yAxis.tick, fill: INK_MUTED }} />
            <Tooltip content={<QtyTooltip />} cursor={{ fill: '#0d825610' }} />
            <Bar dataKey="qty" fill={BRAND} barSize={40} radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 12, fill: INK_MUTED }} />
          </BarChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  );
}

/** Bảng chéo phòng × loại mẫu — đúng bảng Văn phòng hay phải tự lập bằng tay. */
function PivotCard({ view }: { view: View }) {
  const colTotal = (m: TestMatrix) => view.pivotRows.reduce((s, r) => s + (r.cells.get(m) ?? 0), 0);
  return (
    <Card>
      <CardHeader title="Số mẫu theo phòng × loại mẫu" subtitle="Ô trống = phòng không có mẫu loại đó" />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-plate text-left text-xs uppercase text-subink">
            <tr>
              <th className="px-4 py-2.5 font-medium">Phòng nghiên cứu</th>
              {view.pivotCols.map((c) => (
                <th key={c.matrix} className="px-3 py-2.5 text-right font-medium">
                  {c.label}
                </th>
              ))}
              <th className="px-4 py-2.5 text-right font-semibold text-ink">Tổng</th>
            </tr>
          </thead>
          <tbody>
            {view.pivotRows.map((r) => (
              <tr key={r.id} className="border-t border-hairline">
                <td className="px-4 py-2 text-ink">{r.name}</td>
                {view.pivotCols.map((c) => (
                  <td key={c.matrix} className="px-3 py-2 text-right tabular-nums text-ink">
                    {r.cells.get(c.matrix) ? formatNumber(r.cells.get(c.matrix) as number) : ''}
                  </td>
                ))}
                <td className="px-4 py-2 text-right font-semibold tabular-nums text-ink">
                  {r.total ? formatNumber(r.total) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-hairline bg-plate/60 font-semibold text-ink">
              <td className="px-4 py-2.5">Tổng</td>
              {view.pivotCols.map((c) => (
                <td key={c.matrix} className="px-3 py-2.5 text-right tabular-nums">
                  {formatNumber(colTotal(c.matrix))}
                </td>
              ))}
              <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(view.totalQty)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  );
}

function TopCriteriaCard({ top }: { top: { name: string; items: number }[] }) {
  if (top.length === 0) return null;
  const max = top[0].items;
  return (
    <Card>
      <CardHeader title="Chỉ tiêu phân tích nhiều nhất" subtitle="Đếm số mã mẫu có phân tích chỉ tiêu đó" />
      <CardBody>
        <ol className="flex flex-col gap-2">
          {top.map((t, i) => (
            <li key={t.name} className="grid grid-cols-[24px_minmax(0,1fr)_minmax(60px,35%)_40px] items-center gap-3 text-sm">
              <span className="text-right text-xs text-subink">{i + 1}</span>
              <span className="truncate text-ink" title={t.name}>
                {t.name}
              </span>
              <span className="h-2 rounded-full bg-plate">
                <span className="block h-2 rounded-full" style={{ width: `${(t.items / max) * 100}%`, background: BRAND }} />
              </span>
              <span className="text-right tabular-nums text-ink">{t.items}</span>
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}
