import { useState } from 'react';
import { Receipt, Plus, Pencil, Trash2, FileSpreadsheet, Send, Eye } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { DescList, DescItem, DescPeriod } from '@/components/ui/DescList';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDate, formatMoney } from '@/lib/format';
import { canManageQuotations } from '@/lib/rbac';
import {
  QUOTATION_STATUS_LABELS,
  TEST_MATRIX_LABELS,
  type Quotation,
  type QuotationItem,
  type QuotationStatus,
  type TestMatrix,
} from '@/types';
import * as quoApi from '@/api/quotation';
import * as flowApi from '@/api/sampleFlow';

const TONE: Record<QuotationStatus, BadgeTone> = {
  draft: 'muted',
  sent: 'pending',
  accepted: 'success',
  rejected: 'overdue',
  expired: 'warning',
};

export function QuotationStatusBadge({ status }: { status: QuotationStatus }) {
  return <Badge tone={TONE[status] ?? 'neutral'}>{QUOTATION_STATUS_LABELS[status] ?? status}</Badge>;
}

/** m29 — Trang BÁO GIÁ: lập, sửa, đổi trạng thái, xuất Excel theo mẫu Viện. */
export function Quotations() {
  const { user } = useAuth();
  const toast = useToast();
  const canManage = canManageQuotations(user);

  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [statusFilter, setStatusFilter] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Quotation | null>(null);
  const [viewId, setViewId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Quotation | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => quoApi.listQuotations({ q: dq || undefined, status: statusFilter || undefined, limit: 100 }),
    [dq, statusFilter],
  );

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await quoApi.deleteQuotation(deleteTarget.id);
      toast.success('Đã xóa báo giá');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setDeleting(false);
    }
  }

  async function exportXlsx(row: Quotation) {
    try {
      await quoApi.exportQuotationXlsx(row.id);
      toast.success('Đã tải bảng báo giá (.xlsx)');
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  const columns: Column<Quotation>[] = [
    { key: 'code', header: 'Số báo giá', render: (r) => <span className="font-semibold text-ink">{r.code}</span> },
    {
      key: 'customer', header: 'Khách hàng',
      render: (r) => (
        <div className="min-w-0">
          <div className="truncate font-medium text-ink">{r.customer_name}</div>
          {r.intake_code && <div className="text-xs text-subink">Phiếu: {r.intake_code}</div>}
        </div>
      ),
    },
    { key: 'issue', header: 'Ngày lập', render: (r) => (r.issue_date ? formatDate(r.issue_date) : '—') },
    { key: 'valid', header: 'Hiệu lực đến', render: (r) => (r.valid_until ? formatDate(r.valid_until) : '—') },
    {
      key: 'total', header: 'Tổng cộng', align: 'right',
      sortValue: (r) => Number(r.total),
      render: (r) => <span className="font-semibold text-ink">{formatMoney(r.total)}</span>,
    },
    { key: 'status', header: 'Trạng thái', render: (r) => <QuotationStatusBadge status={r.status} /> },
    {
      key: 'actions', header: '', align: 'right',
      render: (r) => (
        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="ghost" title="Xem chi tiết" onClick={() => setViewId(r.id)}>
            <Eye size={14} />
          </Button>
          <Button size="sm" variant="ghost" title="Xuất Excel" onClick={() => exportXlsx(r)}>
            <FileSpreadsheet size={14} className="text-success" />
          </Button>
          {canManage && r.status !== 'accepted' && (
            <>
              <Button size="sm" variant="ghost" title="Sửa" onClick={() => setEditTarget(r)}>
                <Pencil size={14} />
              </Button>
              <Button size="sm" variant="ghost" title="Xóa" onClick={() => setDeleteTarget(r)}>
                <Trash2 size={14} className="text-overdue" />
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Báo giá"
        description="Lập bảng báo giá gửi khách hàng · xuất Excel theo mẫu của Viện"
        icon={<Receipt size={20} />}
        actions={canManage && <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Lập báo giá</Button>}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Số báo giá / khách hàng…" className="max-w-xs" />
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full sm:max-w-[190px]">
            <option value="">— Mọi trạng thái —</option>
            {(Object.keys(QUOTATION_STATUS_LABELS) as QuotationStatus[]).map((s) => (
              <option key={s} value={s}>{QUOTATION_STATUS_LABELS[s]}</option>
            ))}
          </Select>
          <span className="ml-auto text-sm text-subink">{data?.meta?.total ?? 0} báo giá</span>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(r) => r.id}
          loading={loading}
          pageSize={15}
          onRowClick={(r) => setViewId(r.id)}
        />
      </Card>

      {createOpen && (
        <QuotationModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => { setCreateOpen(false); reload(); toast.success('Đã lập báo giá'); }}
        />
      )}
      {editTarget && (
        <QuotationModal
          quotationId={editTarget.id}
          onClose={() => setEditTarget(null)}
          onSaved={() => { setEditTarget(null); reload(); toast.success('Đã cập nhật báo giá'); }}
        />
      )}
      {viewId && (
        <QuotationDetail
          quotationId={viewId}
          canManage={canManage}
          onClose={() => setViewId(null)}
          onChanged={reload}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa báo giá"
        message={`Xóa báo giá ${deleteTarget?.code ?? ''}?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

// ===== Chi tiết + đổi trạng thái + xuất Excel =====
function QuotationDetail({
  quotationId, canManage, onClose, onChanged,
}: {
  quotationId: string; canManage: boolean; onClose: () => void; onChanged: () => void;
}) {
  const toast = useToast();
  const { data: q, loading, reload } = useAsync(() => quoApi.getQuotation(quotationId), [quotationId]);
  const [busy, setBusy] = useState<string | null>(null);

  async function go(s: QuotationStatus) {
    setBusy(s);
    try {
      await quoApi.changeQuotationStatus(quotationId, s);
      toast.success(`Đã chuyển sang "${QUOTATION_STATUS_LABELS[s]}"`);
      reload();
      onChanged();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={q ? `Báo giá ${q.code}` : 'Báo giá'}
      description={q?.customer_name}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Đóng</Button>
          {q && (
            <Button
              onClick={async () => {
                try {
                  await quoApi.exportQuotationXlsx(q.id);
                  toast.success('Đã tải bảng báo giá (.xlsx)');
                } catch (err) {
                  toast.error(describeError(err).title);
                }
              }}
            >
              <FileSpreadsheet size={15} /> Xuất Excel
            </Button>
          )}
        </>
      }
    >
      {loading || !q ? (
        <div className="py-8 text-center text-sm text-subink">Đang tải…</div>
      ) : (
        <div className="flex flex-col gap-4">
          {/* Trước đây là lối viết "Nhãn: giá trị" inline — lối thứ ba trong ứng dụng
              cho cùng một việc. Gom về DescList để modal xem ở mọi module đọc như một. */}
          <DescList>
            <DescItem label="Khách hàng" value={q.customer_name} />
            <DescItem label="Trạng thái" value={<QuotationStatusBadge status={q.status} />} />
            <DescItem full label="Địa chỉ" value={q.customer_address} />
            <DescItem label="Email" value={q.customer_email} />
            <DescItem label="Điện thoại" value={q.customer_phone} />
            <DescPeriod label="Hiệu lực" from={q.issue_date} to={q.valid_until} />
          </DescList>

          {/* Bảng chi tiết đúng thứ tự cột mẫu báo giá */}
          <div className="overflow-x-auto rounded-lg border border-hairline scrollbar-thin">
            <table className="w-full min-w-[640px] border-collapse text-xs table-sticky-1">
              <thead className="bg-plate text-subink">
                <tr>
                  <th className="w-10 px-2 py-1.5 text-center">STT</th>
                  <th className="px-2 py-1.5 text-left">Loại/Tên mẫu</th>
                  <th className="px-2 py-1.5 text-left">Chỉ tiêu thử nghiệm</th>
                  <th className="w-16 px-2 py-1.5 text-center">SL</th>
                  <th className="px-2 py-1.5 text-right">Đơn giá</th>
                  <th className="px-2 py-1.5 text-right">Thành tiền</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {(q.items ?? []).map((it, i) => (
                  <tr key={it.id ?? i}>
                    <td className="px-2 py-1.5 text-center text-subink">{i + 1}</td>
                    <td className="px-2 py-1.5 text-ink">{it.sample_name ?? '—'}</td>
                    <td className="px-2 py-1.5 font-medium text-ink">{it.parameter_name}</td>
                    <td className="px-2 py-1.5 text-center">{it.quantity}</td>
                    <td className="px-2 py-1.5 text-right">{formatMoney(it.unit_price)}</td>
                    <td className="px-2 py-1.5 text-right font-medium text-ink">{formatMoney(it.amount ?? '0')}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-hairline">
                <tr><td colSpan={5} className="px-2 py-1.5 text-right text-subink">Cộng:</td>
                  <td className="px-2 py-1.5 text-right font-medium text-ink">{formatMoney(q.subtotal)}</td></tr>
                <tr><td colSpan={5} className="px-2 py-1.5 text-right text-subink">VAT {q.vat_rate.replace(/\.?0+$/, '')}%:</td>
                  <td className="px-2 py-1.5 text-right font-medium text-ink">{formatMoney(q.vat_amount)}</td></tr>
                <tr><td colSpan={5} className="px-2 py-1.5 text-right font-semibold text-ink">Tổng cộng:</td>
                  <td className="px-2 py-1.5 text-right text-base font-bold text-ink">{formatMoney(q.total)}</td></tr>
              </tfoot>
            </table>
          </div>

          {q.note && <p className="text-sm"><span className="text-subink">Ghi chú:</span> {q.note}</p>}

          {canManage && (q.next_statuses?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
              <span className="text-xs text-subink">Chuyển trạng thái:</span>
              {q.next_statuses!.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={s === 'accepted' ? 'success' : s === 'rejected' ? 'secondary' : 'primary'}
                  loading={busy === s}
                  onClick={() => go(s)}
                >
                  {s === 'sent' && <Send size={13} />} {QUOTATION_STATUS_LABELS[s]}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// ===== Form lập / sửa báo giá =====
type Row = QuotationItem & { _key: string };

function QuotationModal({
  quotationId, onClose, onSaved,
}: {
  quotationId?: string; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!quotationId;
  const { data: existing } = useAsync(
    () => (quotationId ? quoApi.getQuotation(quotationId) : Promise.resolve(null)),
    [quotationId],
  );

  const [f, setF] = useState({
    customer_name: '', customer_address: '', customer_email: '', customer_phone: '',
    issue_date: '', valid_until: '', vat_rate: '8', note: '',
  });
  const [rows, setRows] = useState<Row[]>([]);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Nạp dữ liệu khi sửa
  if (editing && existing && !loaded) {
    setF({
      customer_name: existing.customer_name ?? '',
      customer_address: existing.customer_address ?? '',
      customer_email: existing.customer_email ?? '',
      customer_phone: existing.customer_phone ?? '',
      issue_date: existing.issue_date ?? '',
      valid_until: existing.valid_until ?? '',
      vat_rate: existing.vat_rate ?? '8',
      note: existing.note ?? '',
    });
    setRows((existing.items ?? []).map((it, i) => ({ ...it, _key: `e${i}` })));
    setLoaded(true);
  }

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  // Tổng tiền hiển thị tạm (server sẽ tính lại khi lưu)
  const subtotal = rows.reduce((s, r) => s + Number(r.unit_price || 0) * Number(r.quantity || 1), 0);
  const vat = (subtotal * Number(f.vat_rate || 0)) / 100;

  function addRow() {
    setRows((p) => [
      ...p,
      { _key: `n${Date.now()}`, sample_name: '', parameter_name: '', quantity: 1, unit_price: '0' },
    ]);
  }
  function upRow(key: string, patch: Partial<QuotationItem>) {
    setRows((p) => p.map((r) => (r._key === key ? { ...r, ...patch } : r)));
  }

  async function submit() {
    if (!f.customer_name.trim()) return toast.error('Nhập tên khách hàng');
    if (rows.length === 0) return toast.error('Thêm ít nhất 1 dòng chỉ tiêu');
    if (rows.some((r) => !r.parameter_name.trim())) return toast.error('Có dòng chưa nhập tên chỉ tiêu');
    setSaving(true);
    try {
      const body = {
        customer_name: f.customer_name.trim(),
        customer_address: f.customer_address.trim() || null,
        customer_email: f.customer_email.trim() || null,
        customer_phone: f.customer_phone.trim() || null,
        issue_date: f.issue_date || null,
        valid_until: f.valid_until || null,
        vat_rate: f.vat_rate || '8',
        note: f.note.trim() || null,
        items: rows.map(({ _key, ...r }, i) => ({ ...r, sort_order: i })),
      };
      if (editing) await quoApi.updateQuotation(quotationId!, body);
      else await quoApi.createQuotation(body);
      onSaved();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={editing ? 'Sửa báo giá' : 'Lập bảng báo giá'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button onClick={submit} loading={saving}>{editing ? 'Lưu' : 'Lập báo giá'}</Button>
        </>
      }
    >
      <FormBody>
        <FormSection title="Khách hàng">
          <Field label="Tên khách hàng" required className="md:col-span-2">
            <Input value={f.customer_name} onChange={set('customer_name')} placeholder="CÔNG TY TNHH …" />
          </Field>
          <Field label="Địa chỉ" className="md:col-span-2">
            <Input value={f.customer_address} onChange={set('customer_address')} />
          </Field>
          <Field label="Email"><Input value={f.customer_email} onChange={set('customer_email')} /></Field>
          <Field label="Điện thoại"><Input value={f.customer_phone} onChange={set('customer_phone')} /></Field>
        </FormSection>

        <FormSection title="Hiệu lực & thuế">
          <Field label="Ngày lập"><Input type="date" value={f.issue_date} onChange={set('issue_date')} /></Field>
          <Field label="Hiệu lực đến" hint="Mặc định 1 tháng">
            <Input type="date" value={f.valid_until} onChange={set('valid_until')} />
          </Field>
          <Field label="VAT (%)" hint="Mặc định 8% — sửa được">
            <Input value={f.vat_rate} onChange={set('vat_rate')} />
          </Field>
        </FormSection>

        {/* Dòng chi tiết — khối riêng, tự quản lý tiêu đề và nút thêm dòng */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-ink">Chi tiết báo giá ({rows.length})</span>
            <div className="flex gap-2">
              <PickFromCatalog onPick={(it) => setRows((p) => [...p, { ...it, _key: `c${Date.now()}${p.length}` }])} />
              <Button size="sm" variant="secondary" onClick={addRow}><Plus size={14} /> Dòng trống</Button>
            </div>
          </div>
          {rows.length === 0 ? (
            <p className="rounded-lg border border-hairline p-3 text-sm text-subink">
              Chưa có dòng nào — bấm "Chọn từ danh mục" để lấy chỉ tiêu kèm đơn giá, hoặc "Dòng trống" để nhập tay.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {rows.map((r, i) => (
                <div key={r._key} className="grid grid-cols-12 items-end gap-2 rounded-lg border border-hairline p-2">
                  <span className="col-span-12 text-xs text-subink sm:col-span-1">#{i + 1}</span>
                  <Field label="Loại/Tên mẫu" className="col-span-12 sm:col-span-3">
                    <Input value={r.sample_name ?? ''} onChange={(e) => upRow(r._key, { sample_name: e.target.value })} />
                  </Field>
                  <Field label="Chỉ tiêu" required className="col-span-12 sm:col-span-4">
                    <Input value={r.parameter_name} onChange={(e) => upRow(r._key, { parameter_name: e.target.value })} />
                  </Field>
                  <Field label="SL" className="col-span-4 sm:col-span-1">
                    <Input type="number" min={1} value={r.quantity}
                      onChange={(e) => upRow(r._key, { quantity: Number(e.target.value) || 1 })} />
                  </Field>
                  <Field label="Đơn giá" className="col-span-6 sm:col-span-2">
                    <Input value={r.unit_price} onChange={(e) => upRow(r._key, { unit_price: e.target.value })} />
                  </Field>
                  <div className="col-span-2 sm:col-span-1">
                    <Button size="sm" variant="ghost" onClick={() => setRows((p) => p.filter((x) => x._key !== r._key))}>
                      <Trash2 size={14} className="text-overdue" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Tổng tiền (tạm tính — server chốt lại) */}
        <div className="flex flex-col gap-1 rounded-lg bg-plate p-3 text-sm">
          <div className="flex justify-between"><span className="text-subink">Cộng:</span>
            <span className="font-medium text-ink">{formatMoney(String(subtotal))}</span></div>
          <div className="flex justify-between"><span className="text-subink">VAT {f.vat_rate || 0}%:</span>
            <span className="font-medium text-ink">{formatMoney(String(vat))}</span></div>
          <div className="flex justify-between border-t border-hairline pt-1">
            <span className="font-semibold text-ink">Tổng cộng:</span>
            <span className="text-base font-bold text-ink">{formatMoney(String(subtotal + vat))}</span></div>
        </div>

        <FormSection title="Ghi chú" cols={1}>
          <Field label="Ghi chú thêm (in vào báo giá)">
            <Textarea rows={2} value={f.note} onChange={set('note')} />
          </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}

/** Chọn chỉ tiêu từ danh mục 614 chỉ tiêu → tự điền tên/phương pháp/đơn giá. */
function PickFromCatalog({ onPick }: { onPick: (it: QuotationItem) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [matrix, setMatrix] = useState('');
  const { data, loading } = useAsync(
    () => flowApi.listTestParameters({ q: dq || undefined, matrix: matrix || undefined, is_active: true, limit: 30 }),
    [dq, matrix],
  );

  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        <Plus size={14} /> Chọn từ danh mục
      </Button>
      {open && (
        <Modal
          open
          onClose={() => setOpen(false)}
          title="Chọn chỉ tiêu từ danh mục"
          description="Bấm để thêm vào báo giá (đơn giá lấy từ bảng giá, sửa được sau)"
          footer={<Button variant="secondary" onClick={() => setOpen(false)}>Xong</Button>}
        >
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-2">
              <SearchInput value={q} onChange={setQ} placeholder="Tìm chỉ tiêu…" className="w-full sm:min-w-[200px] sm:flex-1" />
              <Select value={matrix} onChange={(e) => setMatrix(e.target.value)} className="w-full sm:max-w-[200px]">
                <option value="">— Mọi nền mẫu —</option>
                {(Object.keys(TEST_MATRIX_LABELS) as TestMatrix[]).map((m) => (
                  <option key={m} value={m}>{TEST_MATRIX_LABELS[m]}</option>
                ))}
              </Select>
            </div>
            <div className="max-h-72 overflow-y-auto rounded-lg border border-hairline scrollbar-thin">
              {loading ? (
                <p className="p-3 text-sm text-subink">Đang tải…</p>
              ) : (
                <ul className="divide-y divide-hairline">
                  {(data?.data ?? []).map((p) => (
                    <li key={p.id}>
                      <button
                        onClick={() =>
                          onPick({
                            sample_name: p.sample_matrix ?? '',
                            test_parameter_id: p.id,
                            parameter_name: p.name,
                            method: p.method,
                            unit: p.unit,
                            quantity: 1,
                            unit_price: p.unit_price ?? '0',
                          })
                        }
                        className="flex w-full items-start justify-between gap-3 px-3 py-2 text-left hover:bg-plate"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium text-ink">{p.name}</span>
                          <span className="block truncate text-xs text-subink">
                            {p.matrix_label}{p.method ? ` · ${p.method}` : ''}
                          </span>
                        </span>
                        <span className="shrink-0 text-xs font-medium text-ink">
                          {p.unit_price ? formatMoney(p.unit_price) : '—'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
