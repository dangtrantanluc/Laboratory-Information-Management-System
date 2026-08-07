import { useState } from 'react';
import { ErrorState } from '@/components/ui/States';
import { useNavigate } from 'react-router-dom';
import { ClipboardList, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { CustomerPicker } from '@/components/ui/CustomerPicker';
import { RequestStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canCreateSample } from '@/lib/rbac';
import * as samplesApi from '@/api/samples';
import type { TestRequestListItem } from '@/types';

export function SampleRequests() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [status, setStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => samplesApi.listRequests({ q: dq || undefined, status: status || undefined, limit: 100 }),
    [dq, status],
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
      priority: 1,
      header: 'Ngày nhận',
      sortValue: (r) => r.received_at,
      render: (r) => formatDate(r.received_at),
    },
    { key: 'status', priority: 1, header: 'Trạng thái', render: (r) => <RequestStatusBadge status={r.status} /> },
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
          <SearchInput value={q} onChange={setQ} placeholder="Mã phiếu / khách / người gửi…" className="w-full sm:max-w-xs sm:flex-1" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full sm:max-w-[180px]">
            <option value="">Mọi trạng thái</option>
            <option value="draft">Nháp</option>
            <option value="active">Đang xử lý</option>
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          knownTotal={data?.meta?.total}
          empty={error ? <ErrorState error={error} onRetry={reload} /> : undefined}
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
  // m33 — thay <Select> nạp sẵn 100 khách bằng ô tra cứu: dropdown cũ cắt cứng ở
  // khách thứ 100 và không báo gì, khách thứ 101 trở đi đơn giản là không chọn được.
  const [customerName, setCustomerName] = useState('');
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!senderName.trim()) {
      toast.error('Nhập tên người gửi');
      return;
    }
    setSubmitting(true);
    try {
      const r = await samplesApi.createRequest({
        sender_name: senderName.trim(),
        customer_id: customerId,
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
        <Field label="Khách hàng" hint="Có thể bỏ trống nếu khách nội bộ chưa có trong sổ">
          <CustomerPicker
            name={customerName}
            customerId={customerId}
            onNameChange={(v) => {
              setCustomerId(null);
              setCustomerName(v);
            }}
            onPick={(c) => {
              setCustomerId(c.id);
              setCustomerName(c.name);
              // Người gửi thường là người liên hệ của khách — điền sẵn, vẫn sửa được.
              if (!senderName.trim() && c.contact_person) setSenderName(c.contact_person);
            }}
          />
        </Field>
        <Field label="Tên người gửi mẫu" required>
          <Input value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="Nguyễn Văn A" />
        </Field>
        <Field label="Ghi chú">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú chung của phiếu" />
        </Field>
      </div>
    </Modal>
  );
}
