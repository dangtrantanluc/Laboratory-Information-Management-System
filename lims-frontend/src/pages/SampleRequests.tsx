import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardList, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { RequestStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canCreateSample } from '@/lib/rbac';
import * as samplesApi from '@/api/samples';
import * as customersApi from '@/api/customers';
import type { TestRequestListItem } from '@/types';

export function SampleRequests() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () => samplesApi.listRequests({ q: q || undefined, status: status || undefined, limit: 100 }),
    [q, status],
  );

  const columns: Column<TestRequestListItem>[] = [
    {
      key: 'request_code',
      header: 'Mã phiếu',
      sortValue: (r) => r.request_code,
      render: (r) => <span className="font-semibold text-ink">{r.request_code}</span>,
    },
    {
      key: 'customer',
      header: 'Khách / Người gửi',
      render: (r) => (
        <div>
          <p className="text-ink">{r.customer_name ?? r.sender_name}</p>
          {r.customer_name && <p className="text-xs text-subink">{r.sender_name}</p>}
        </div>
      ),
    },
    { key: 'department_name', header: 'Phòng', render: (r) => r.department_name ?? '—' },
    {
      key: 'sample_count',
      header: 'Số mẫu',
      align: 'center',
      sortValue: (r) => r.sample_count,
      render: (r) => r.sample_count,
    },
    {
      key: 'received_at',
      header: 'Ngày nhận',
      sortValue: (r) => r.received_at,
      render: (r) => formatDate(r.received_at),
    },
    { key: 'status', header: 'Trạng thái', render: (r) => <RequestStatusBadge status={r.status} /> },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Phiếu yêu cầu thử nghiệm"
        description="Quản lý phiếu tiếp nhận và các mẫu thử nghiệm"
        icon={<ClipboardList size={20} />}
        actions={
          canCreateSample(user) ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Tạo phiếu
            </Button>
          ) : undefined
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Mã phiếu / khách / người gửi…" className="max-w-xs flex-1" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-[180px]">
            <option value="">Mọi trạng thái</option>
            <option value="draft">Nháp</option>
            <option value="active">Đang xử lý</option>
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(r) => r.id}
          loading={loading}
          pageSize={12}
          onRowClick={(r) => navigate(`/samples/request/${r.id}`)}
        />
      </Card>

      {createOpen && (
        <CreateRequestModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => {
            setCreateOpen(false);
            reload();
            toast.success('Đã tạo phiếu');
            navigate(`/samples/request/${id}`);
          }}
        />
      )}
    </div>
  );
}

function CreateRequestModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const toast = useToast();
  const [senderName, setSenderName] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: customers } = useAsync(() => customersApi.listCustomers({ limit: 100 }), []);

  async function submit() {
    if (!senderName.trim()) {
      toast.error('Nhập tên người gửi');
      return;
    }
    setSubmitting(true);
    try {
      const r = await samplesApi.createRequest({
        sender_name: senderName.trim(),
        customer_id: customerId || null,
        note: note || null,
      });
      onCreated(r.id);
    } catch (err) {
      const { title } = describeError(err);
      toast.error(title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Tạo phiếu yêu cầu thử nghiệm"
      description="Sau khi tạo phiếu, thêm các mẫu trong trang chi tiết."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo phiếu
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Tên người gửi mẫu" required>
          <Input value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="Nguyễn Văn A" />
        </Field>
        <Field label="Khách hàng" hint="Có thể bỏ trống nếu khách nội bộ chưa tạo">
          <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">— Không chọn —</option>
            {(customers?.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ghi chú">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú chung của phiếu" />
        </Field>
      </div>
    </Modal>
  );
}
