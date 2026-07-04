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
import { describeError } from '@/lib/errors';
import { canManageCustomers } from '@/lib/rbac';
import { CUSTOMER_TYPE_LABELS, type Customer } from '@/types';
import * as customersApi from '@/api/customers';

export function Customers() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState<Customer | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading, reload } = useAsync(
    () => customersApi.listCustomers({ q: q || undefined, limit: 100 }),
    [q],
  );

  const canManage = canManageCustomers(user);
  const columns: Column<Customer>[] = [
    { key: 'name', header: 'Tên', sortValue: (c) => c.name, render: (c) => <span className="font-semibold text-ink">{c.name}</span> },
    { key: 'contact', header: 'Liên hệ', render: (c) => c.contact ?? '—' },
    {
      key: 'type',
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
  const [name, setName] = useState(customer?.name ?? '');
  const [contact, setContact] = useState(customer?.contact ?? '');
  const [type, setType] = useState(customer?.type ?? 'company');
  const [note, setNote] = useState(customer?.note ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!name.trim()) return toast.error('Nhập tên khách hàng');
    setSubmitting(true);
    try {
      const body = { name: name.trim(), contact: contact || null, type, note: note || null };
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
        <Field label="Tên" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Liên hệ (SĐT/email)">
          <Input value={contact} onChange={(e) => setContact(e.target.value)} />
        </Field>
        <Field label="Loại">
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="company">Công ty</option>
            <option value="organization">Tổ chức</option>
            <option value="individual">Cá nhân</option>
            <option value="internal">Nội bộ</option>
            <option value="external">Bên ngoài</option>
          </Select>
        </Field>
        <Field label="Ghi chú">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
