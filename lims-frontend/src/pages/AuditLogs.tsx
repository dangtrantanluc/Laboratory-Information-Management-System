import { useState } from 'react';
import { ScrollText } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Input } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { useAsync } from '@/lib/useAsync';
import { formatDateTime } from '@/lib/format';
import * as auditApi from '@/api/audit';
import type { AuditLog } from '@/types';

export function AuditLogs() {
  const [action, setAction] = useState('');
  const [resource, setResource] = useState('');
  const { data, loading } = useAsync(
    () => auditApi.listAuditLogs({ action: action || undefined, resource: resource || undefined, limit: 100 }),
    [action, resource],
  );

  const columns: Column<AuditLog>[] = [
    { key: 'at', header: 'Thời gian', sortValue: (a) => a.at, render: (a) => <span className="whitespace-nowrap text-subink">{formatDateTime(a.at)}</span> },
    { key: 'user_name', header: 'Người dùng', render: (a) => a.user_name },
    { key: 'action', header: 'Hành động', render: (a) => <Badge tone="neutral">{a.action}</Badge> },
    { key: 'resource', header: 'Đối tượng', render: (a) => `${a.resource}${a.resource_id ? ` · ${a.resource_id.slice(0, 8)}` : ''}` },
    { key: 'ip', header: 'IP', render: (a) => a.ip ?? '—' },
    {
      key: 'correlation_id',
      header: 'Correlation',
      render: (a) => (a.correlation_id ? <code className="text-xs text-stem">{a.correlation_id.slice(0, 8)}</code> : '—'),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Nhật ký hệ thống"
        description="Audit log — chỉ đọc, không thể sửa/xóa"
        icon={<ScrollText size={20} />}
      />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-hairline p-4">
          <Input
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="Lọc theo hành động (vd: SAMPLE_RESULT_ENTER)"
            className="max-w-xs"
          />
          <Input
            value={resource}
            onChange={(e) => setResource(e.target.value)}
            placeholder="Lọc theo đối tượng (vd: sample)"
            className="max-w-xs"
          />
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(a) => a.id} loading={loading} pageSize={15} />
      </Card>
    </div>
  );
}
