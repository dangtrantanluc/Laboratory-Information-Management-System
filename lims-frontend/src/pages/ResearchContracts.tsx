import { useState } from 'react';
import { FileSignature, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatMoney } from '@/lib/format';
import type { ResearchContract } from '@/types';
import { canManageActivities } from '@/lib/rbac';
import * as activityApi from '@/api/activity';

export function ResearchContracts() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ResearchContract | null>(null);
  const [viewTarget, setViewTarget] = useState<ResearchContract | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResearchContract | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(() => activityApi.listContracts({ limit: 100 }), []);
  const canManage = canManageActivities(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await activityApi.deleteContract(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<ResearchContract>[] = [
    { key: 'title', header: 'Tên hợp đồng', render: (c) => <span className="font-medium text-ink">{c.title}</span> },
    { key: 'contract_type', header: 'Loại', render: (c) => c.contract_type ?? '—' },
    { key: 'value', header: 'Giá trị', align: 'right', render: (c) => formatMoney(c.value_amount, c.currency ?? 'VND') },
    { key: 'partner', header: 'Đơn vị phối hợp', render: (c) => c.partner_org ?? '—' },
    { key: 'year', header: 'Năm học', render: (c) => c.academic_year ?? '—' },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: ResearchContract) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(c)}>
                  <Pencil size={14} />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(c)}>
                  <Trash2 size={14} className="text-overdue" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hợp đồng NCKH"
        description="Danh mục hợp đồng nghiên cứu / tư vấn / chuyển giao KHCN"
        icon={<FileSignature size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm hợp đồng
            </Button>
          )
        }
      />
      <Card>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(c) => c.id}
          loading={loading}
          pageSize={12}
          onRowClick={(c) => setViewTarget(c)}
        />
      </Card>

      {createOpen && (
        <ContractModal onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); reload(); toast.success('Đã thêm'); }} />
      )}
      {editTarget && (
        <ContractModal contract={editTarget} onClose={() => setEditTarget(null)} onSaved={() => { setEditTarget(null); reload(); toast.success('Đã cập nhật'); }} />
      )}
      {viewTarget && (
        <ContractDetailModal contract={viewTarget} canManage={canManage} onClose={() => setViewTarget(null)} onEdit={() => { const c = viewTarget; setViewTarget(null); setEditTarget(c); }} />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa hợp đồng"
        message="Xóa hợp đồng này?"
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function ContractDetailModal({ contract: c, canManage, onClose, onEdit }: { contract: ResearchContract; canManage: boolean; onClose: () => void; onEdit: () => void }) {
  return (
    <Modal open onClose={onClose} title="Chi tiết hợp đồng" footer={<><Button variant="secondary" onClick={onClose}>Đóng</Button>{canManage && <Button onClick={onEdit}><Pencil size={14} /> Chỉnh sửa</Button>}</>}>
      <DescList>
        <DescItem full label="Tên hợp đồng" value={c.title} />
        <DescItem label="Loại hợp đồng" value={c.contract_type} />
        <DescItem label="Giá trị" value={formatMoney(c.value_amount, c.currency ?? 'VND')} />
        <DescItem label="Đơn vị phối hợp" value={c.partner_org} />
        <DescItem label="Bắt đầu" value={c.start_date ? formatDate(c.start_date) : '—'} />
        <DescItem label="Kết thúc" value={c.end_date ? formatDate(c.end_date) : '—'} />
        <DescItem label="Năm học" value={c.academic_year} />
        <DescItem label="Phòng ban" value={c.department_name} />
      </DescList>
    </Modal>
  );
}

function ContractModal({ contract, onClose, onSaved }: { contract?: ResearchContract; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const editing = !!contract;
  const [title, setTitle] = useState(contract?.title ?? '');
  const [contractType, setContractType] = useState(contract?.contract_type ?? '');
  const [value, setValue] = useState(contract?.value_amount ?? '');
  const [partner, setPartner] = useState(contract?.partner_org ?? '');
  const [startDate, setStartDate] = useState(contract?.start_date ?? '');
  const [endDate, setEndDate] = useState(contract?.end_date ?? '');
  const [academicYear, setAcademicYear] = useState(contract?.academic_year ?? '');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tên hợp đồng');
    setSubmitting(true);
    try {
      const body = {
        title: title.trim(),
        contract_type: contractType || null,
        value_amount: value || null,
        partner_org: partner || null,
        start_date: startDate || null,
        end_date: endDate || null,
        academic_year: academicYear || null,
      };
      if (editing) await activityApi.updateContract(contract!.id, body);
      else await activityApi.createContract(body);
      onSaved();
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
      title={editing ? 'Sửa hợp đồng' : 'Thêm hợp đồng'}
      footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button onClick={submit} loading={submitting}>{editing ? 'Lưu' : 'Thêm'}</Button></>}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Tên hợp đồng" required className="md:col-span-2"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Loại hợp đồng"><Input value={contractType} onChange={(e) => setContractType(e.target.value)} placeholder="Nghiên cứu / Tư vấn KHCN…" /></Field>
        <Field label="Giá trị (VND)"><Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="110000000" inputMode="decimal" /></Field>
        <Field label="Đơn vị phối hợp"><Input value={partner} onChange={(e) => setPartner(e.target.value)} /></Field>
        <Field label="Năm học"><Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" /></Field>
        <Field label="Bắt đầu"><Input type="date" value={startDate ?? ''} onChange={(e) => setStartDate(e.target.value)} /></Field>
        <Field label="Kết thúc"><Input type="date" value={endDate ?? ''} onChange={(e) => setEndDate(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
