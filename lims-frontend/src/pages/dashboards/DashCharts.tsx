import { useMemo } from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { useChartHeight, useChartCompact } from '@/lib/useChart';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { SAMPLE_STATUS_LABELS, MEASUREMENT_GROUP_LABELS } from '@/types';

const PIE_COLORS = ['#0d8256', '#0e7c86', '#d97706', '#2563eb', '#dc2626', '#7c3aed'];

export function SamplesByStatusCard({ charts, loading }: { charts: any; loading?: boolean }) {
  const block = charts?.samples_by_status;
  const chartH = useChartHeight();
  const { isMobile } = useChartCompact();
  const data = useMemo(
    () => (block?.data ?? []).map((p: any) => ({ name: (SAMPLE_STATUS_LABELS as Record<string, string>)[p.status] ?? p.status, value: p.count })),
    [block],
  );
  if (!block?.available) return null;
  return (
    <Card>
      <CardHeader title="Mẫu theo trạng thái" subtitle="Phân bố trạng thái mẫu" />
      <CardBody>
        {loading ? <LoadingState /> : data.length === 0 ? <EmptyState title="Chưa có dữ liệu mẫu" /> : (
          <ResponsiveContainer width="100%" height={chartH}>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={isMobile ? 68 : 95} label={isMobile ? false : (e: any) => `${e.name}: ${e.value}`} labelLine={false} fontSize={11}>
                {data.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}

export function SamplesOverTimeCard({ charts, loading, title = 'Mẫu theo thời gian', subtitle = 'Số mẫu tiếp nhận theo kỳ' }: { charts: any; loading?: boolean; title?: string; subtitle?: string }) {
  const block = charts?.samples_over_time;
  const chartH = useChartHeight();
  const { xAxis, yAxis } = useChartCompact();
  const data = useMemo(() => (block?.data ?? []).map((p: any) => ({ name: p.period, value: p.count })), [block]);
  if (!block?.available) return null;
  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} />
      <CardBody>
        {loading ? <LoadingState /> : data.length === 0 ? <EmptyState title="Chưa có dữ liệu" /> : (
          <ResponsiveContainer width="100%" height={chartH}>
            <LineChart data={data} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dceae3" vertical={false} />
              <XAxis dataKey="name" {...xAxis} tick={{ ...xAxis.tick, fill: '#6b7a72' }} />
              <YAxis allowDecimals={false} {...yAxis} tick={{ ...yAxis.tick, fill: '#6b7a72' }} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#0d8256" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}

export function ChemicalConsumptionCard({ charts, loading, className }: { charts: any; loading?: boolean; className?: string }) {
  const block = charts?.chemical_consumption;
  const chartH = useChartHeight();
  const { xAxis, yAxis, legend } = useChartCompact();
  const groups = block?.by_measurement_group ?? [];
  const keys = groups.map((g: any) => `${(MEASUREMENT_GROUP_LABELS as Record<string, string>)[g.measurement_group] ?? g.measurement_group} (${g.base_unit})`);
  const data = useMemo(() => {
    const byPeriod = new Map<string, Record<string, number | string>>();
    for (const g of groups) {
      const key = `${(MEASUREMENT_GROUP_LABELS as Record<string, string>)[g.measurement_group] ?? g.measurement_group} (${g.base_unit})`;
      for (const pt of g.data) {
        const row: Record<string, number | string> = byPeriod.get(pt.period) ?? { name: pt.period };
        row[key] = pt.qty;
        byPeriod.set(pt.period, row);
      }
    }
    return Array.from(byPeriod.values());
  }, [groups]);
  if (!block?.available) return null;
  return (
    <Card className={className}>
      <CardHeader title="Tiêu hao hóa chất theo tháng" subtitle="Tách theo nhóm đo lường (không cộng gộp khác đơn vị)" />
      <CardBody>
        {loading ? <LoadingState /> : data.length === 0 ? <EmptyState title="Chưa có dữ liệu tiêu hao" /> : (
          <ResponsiveContainer width="100%" height={chartH}>
            <BarChart data={data} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dceae3" vertical={false} />
              <XAxis dataKey="name" {...xAxis} tick={{ ...xAxis.tick, fill: '#6b7a72' }} />
              <YAxis {...yAxis} tick={{ ...yAxis.tick, fill: '#6b7a72' }} />
              <Tooltip />
              <Legend {...legend} />
              {keys.map((k: string, i: number) => <Bar key={k} dataKey={k} fill={PIE_COLORS[i % PIE_COLORS.length]} radius={[4, 4, 0, 0]} />)}
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}
