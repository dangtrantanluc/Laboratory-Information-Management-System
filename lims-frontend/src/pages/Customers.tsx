import { useState } from 'react';
import { UserSquare2, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { canManageCustomers } from '@/lib/rbac';
import { CUSTOMER_TYPE_LABELS, type Customer } from '@/types';
import * as customersApi from '@/api/customers';

export function Customers() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () => customersApi.listCustomers({ q: dq || undefined, limit: 100 }),
    [dq],
  );

  const canManage = canManageCustomers(user);
  const columns: Column<Customer>[] = [
    { key: 'name', header: 'Tên', sortValue: (c) => c.name, render: (c) => <span className="font-semibold text-ink">{c.name}</span> },
    { key: 'contact_person', priority: 1, header: 'Người liên hệ', render: (c) => c.contact_person ?? '—' },
    { key: 'phone', priority: 1, header: 'Điện thoại', render: (c) => c.phone ?? c.contact ?? '—' },
    {
      key: 'type',
      priority: 1,
      header: 'Loại',
      render: (c) => <Badge tone="neutral">{CUSTOMER_TYPE_LABELS[c.type] ?? c.type}</Badge>,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Khách hàng"
        description="Đối tượng gửi mẫu thử nghiệm"
        icon={<UserSquare2 size={20} />}
        actions={
          canManage ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm khách hàng
            </Button>
          ) : undefined
        }
      />
      <Card>
        <div className="border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tên / liên hệ…" className="max-w-xs" />
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(c) => c.id}
          loading={loading}
          pageSize={12}
          onRowClick={canManage ? (c) => setEditing(c) : undefined}
        />
      </Card>

      {(createOpen || editing) && (
        <CustomerModal
          customer={editing}
          onClose={() => {
            setCreateOpen(false);
            setEditing(null);
          }}
          onDone={() => {
            setCreateOpen(false);
            setEditing(null);
            reload();
            toast.success('Đã lưu khách hàng');
          }}
        />
      )}
    </div>
  );
}

function CustomerModal({
  customer,
  onClose,
  onDone,
}: {
  customer: Customer | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({
    name: customer?.name ?? '',
    contact: customer?.contact ?? '',
    // 'external' = mặc định của backend (schemas/customer.py) và của DB (server_default).
    type: customer?.type ?? 'external',
    address: customer?.address ?? '',
    tax_code: customer?.tax_code ?? '',
    contact_person: customer?.contact_person ?? '',
    phone: customer?.phone ?? '',
    email: customer?.email ?? '',
    note: customer?.note ?? '',
  });
  const [submitting, setSubmitting] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  async function submit() {
    if (!f.name.trim()) return toast.error('Nhập tên khách hàng');
    setSubmitting(true);
    try {
      const body = {
        name: f.name.trim(),
        contact: f.contact || null,
        type: f.type,
        address: f.address || null,
        tax_code: f.tax_code || null,
        contact_person: f.contact_person || null,
        phone: f.phone || null,
        email: f.email || null,
        note: f.note || null,
      };
      if (customer) await customersApi.updateCustomer(customer.id, body);
      else await customersApi.createCustomer(body);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={customer ? 'Sửa khách hàng' : 'Thêm khách hàng'}
      description="Thông tin ở đây sẽ tự điền vào phiếu nhận mẫu (BM 7.1.01) khi chọn khách này."
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Tên khách hàng / đơn vị" required>
          <Input value={f.name} onChange={set('name')} />
        </Field>
        <Field label="Địa chỉ">
          <Input value={f.address} onChange={set('address')} />
        </Field>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <Field label="Mã số thuế">
            <Input value={f.tax_code} onChange={set('tax_code')} />
          </Field>
          <Field label="Người liên hệ">
            <Input value={f.contact_person} onChange={set('contact_person')} />
          </Field>
          <Field label="Điện thoại">
            <Input value={f.phone} onChange={set('phone')} />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Email">
            <Input value={f.email} onChange={set('email')} />
          </Field>
          <Field label="Loại">
            <Select value={f.type} onChange={set('type')}>
              <option value="external">Bên ngoài</option>
              <option value="organization">Tổ chức / Công ty</option>
              <option value="individual">Cá nhân</option>
              <option value="internal">Nội bộ</option>
            </Select>
          </Field>
        </div>
        <Field label="Liên hệ khác" hint="Ô cũ, giữ lại cho dữ liệu trước đây">
          <Input value={f.contact} onChange={set('contact')} />
        </Field>
        <Field label="Ghi chú">
          <Textarea value={f.note} onChange={set('note')} />
        </Field>
      </div>
    </Modal>
  );
}
