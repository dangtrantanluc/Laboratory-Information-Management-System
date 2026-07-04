import { useState } from 'react';
import { BarChart3, FileSpreadsheet } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Field, Select, Input } from '@/components/ui/Field';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { canExportDocumentStats } from '@/lib/rbac';
import type { TopDocument } from '@/types';
import * as docsApi from '@/api/documents';
import type { AggregateStatsFilters } from '@/api/documents';
import * as usersApi from '@/api/users';

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

export function DocumentAccessStats() {
  const { user } = useAuth();
  const toast = useToast();
  const isStaff = user?.role === 'staff';

  const [departmentId, setDepartmentId] = useState('');
  const [sortBy, setSortBy] = useState<'download' | 'view' | 'edit' | 'total'>('download');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [exporting, setExporting] = useState(false);

  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  function buildFilters(): AggregateStatsFilters {
    return {
      from: from || undefined,
      to: to || undefined,
      department_id: departmentId || undefined,
      sort_by: sortBy,
      top: 20,
    };
  }

  const filters = buildFilters();
  const { data, loading, error } = useAsync(
    () => docsApi.getAccessStatsAggregate(buildFilters()),
    [from, to, departmentId, sortBy],
  );

  async function doExport() {
    if (from && to && from > to) return toast.error('Từ ngày phải trước đến ngày');
    setExporting(true);
    try {
      await docsApi.exportAccessStats(filters);
      toast.success('Đã xuất báo cáo Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const columns: Column<TopDocument>[] = [
    {
      key: 'doc',
      header: 'Tài liệu',
      render: (d) => (
        <div>
          <p className="font-semibold text-ink">{d.title}</p>
          <p className="text-xs text-subink">{d.document_code}</p>
        </div>
      ),
    },
    { key: 'department', header: 'Phòng', render: (d) => d.department_name ?? '—' },
    { key: 'view', header: 'Xem', align: 'right', sortValue: (d) => d.view, render: (d) => d.view },
    { key: 'download', header: 'Tải', align: 'right', sortValue: (d) => d.download, render: (d) => d.download },
    { key: 'edit', header: 'Sửa', align: 'right', sortValue: (d) => d.edit, render: (d) => d.edit },
    {
      key: 'total',
      header: 'Tổng',
      align: 'right',
      sortValue: (d) => d.total,
      render: (d) => <span className="font-semibold text-ink">{d.total}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Thống kê truy cập tài liệu"
        description="Lượt xem / tải / sửa tài liệu và bảng xếp hạng (R15)"
        icon={<BarChart3 size={20} />}
        actions={
          canExportDocumentStats(user) && (
            <Button variant="secondary" onClick={doExport} loading={exporting}>
              <FileSpreadsheet size={16} /> Xuất Excel
            </Button>
          )
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {!isStaff && (
            <Field label="Phòng ban">
              <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                <option value="">Mọi phòng</option>
                {(depts?.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label="Xếp hạng theo">
            <Select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
              <option value="download">Lượt tải</option>
              <option value="view">Lượt xem</option>
              <option value="edit">Lượt sửa</option>
              <option value="total">Tổng truy cập</option>
            </Select>
          </Field>
          <Field label="Từ ngày">
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="Đến ngày">
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </div>
      </Card>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <Card>
          <EmptyState title="Không tải được thống kê" description={describeError(error).title} />
        </Card>
      ) : !data ? (
        <Card>
          <EmptyState title="Chưa có dữ liệu" />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Tổng lượt xem" value={data.summary.total_view} />
            <StatCard label="Tổng lượt tải" value={data.summary.total_download} />
            <StatCard label="Tổng lượt sửa" value={data.summary.total_edit} />
            <StatCard label="Số tài liệu" value={data.summary.document_count} />
          </div>

          <Card>
            <CardHeader title="Tài liệu được truy cập nhiều nhất" subtitle={`Khoảng: ${data.range.from} → ${data.range.to}`} />
            <CardBody className="p-0">
              <DataTable
                columns={columns}
                rows={data.top_documents}
                rowKey={(d) => d.document_id}
                pageSize={20}
                empty={<EmptyState title="Chưa có lượt truy cập trong khoảng thời gian này" />}
              />
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
