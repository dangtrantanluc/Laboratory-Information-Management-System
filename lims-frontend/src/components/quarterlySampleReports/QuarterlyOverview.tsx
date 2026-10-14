/**
 * Tình trạng nộp báo cáo mẫu của mọi phòng lab trong quý — màn hình của Văn phòng.
 * Bấm một phòng để xem chi tiết, trả lại hoặc chốt; xuất Excel toàn Viện ở đây.
 */
import { useState } from 'react';
import { Download } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { ErrorState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import * as api from '@/api/quarterlySampleReports';
import { STATUS_TONE } from './QuarterlyReportPanel';

export function QuarterlyOverview({
  year,
  quarter,
  onOpen,
}: {
  year: number;
  quarter: number;
  onOpen: (departmentId: string) => void;
}) {
  const toast = useToast();
  const { data, loading, error, reload } = useAsync(() => api.getOverview(year, quarter), [year, quarter]);
  const [includeUnlocked, setIncludeUnlocked] = useState(false);
  const [exporting, setExporting] = useState(false);
  const rows = data ?? [];
  const locked = rows.filter((r) => r.status === 'locked').length;
  const submitted = rows.filter((r) => r.status === 'submitted').length;

  async function doExport() {
    setExporting(true);
    try {
      await api.exportQuarterlyReports(year, quarter, includeUnlocked);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const columns: Column<api.QuarterlyOverviewRow>[] = [
    { key: 'stt', header: 'STT', align: 'center', render: (_r, i) => i + 1 },
    {
      key: 'dept',
      header: 'Phòng nghiên cứu',
      sortValue: (r) => r.department.name,
      render: (r) => (
        <div>
          <p className="font-semibold text-ink">{r.department.name}</p>
          <p className="text-xs text-subink">{r.department.code}</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      sortValue: (r) => r.status ?? '',
      render: (r) => (
        <Badge tone={r.status ? STATUS_TONE[r.status] : 'neutral'} dot>
          {r.status_label}
        </Badge>
      ),
    },
    { key: 'items', header: 'Số dòng', align: 'center', sortValue: (r) => r.item_count, render: (r) => r.item_count },
    { key: 'qty', header: 'Số mẫu', align: 'center', sortValue: (r) => r.total_quantity, render: (r) => r.total_quantity },
    { key: 'submitted', header: 'Nộp lúc', render: (r) => formatDateTime(r.submitted_at ?? undefined) },
    { key: 'locked', header: 'Chốt lúc', render: (r) => formatDateTime(r.locked_at ?? undefined) },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline p-4">
        <p className="text-sm text-subink">
          <b className="text-ink">{locked}</b>/{rows.length} phòng đã chốt · <b className="text-ink">{submitted}</b> phòng
          chờ Văn phòng kiểm tra
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-subink">
            <input type="checkbox" checked={includeUnlocked} onChange={(e) => setIncludeUnlocked(e.target.checked)} />
            Gồm cả báo cáo chưa chốt
          </label>
          <Button variant="secondary" onClick={doExport} loading={exporting}>
            <Download size={16} /> Xuất Excel
          </Button>
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.department.id}
        onRowClick={(r) => onOpen(r.department.id)}
        loading={loading}
        pageSize={20}
        empty={error ? <ErrorState error={error} onRetry={reload} /> : undefined}
      />
    </Card>
  );
}
