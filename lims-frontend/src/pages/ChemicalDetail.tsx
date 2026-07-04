import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FlaskConical,
  Plus,
  ArrowDownToLine,
  ArrowUpFromLine,
  Scale,
  FileDown,
  Upload,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { TxnTypeBadge } from '@/components/ui/StatusBadge';
import { SearchInput } from '@/components/ui/SearchInput';
import { AttachmentPanel } from '@/components/ui/AttachmentPanel';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { ApiError } from '@/lib/api';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime, formatDecimal, formatMoney } from '@/lib/format';
import { canTransactChemical, canViewCost } from '@/lib/rbac';
import {
  MEASUREMENT_GROUP_LABELS,
  SAMPLE_STATUS_LABELS,
  type Lot,
  type SampleListItem,
  type TransactionType,
  type Unit,
} from '@/types';
import * as chemApi from '@/api/chemicals';
import * as samplesApi from '@/api/samples';
import type { CreateTransactionBody } from '@/api/chemicals';

export function ChemicalDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const canCost = canViewCost(user);
  const canTxn = canTransactChemical(user);

  const chemQ = useAsync(() => chemApi.getChemical(id), [id]);
  const stockQ = useAsync(() => chemApi.getStock(id), [id]);
  const lotsQ = useAsync(() => chemApi.listLots(id), [id]);
  const txnQ = useAsync(() => chemApi.listTransactions({ chemical_id: id, limit: 100 }), [id]);
  const unitsQ = useAsync(() => chemApi.listUnits(), []);

  const [createLotOpen, setCreateLotOpen] = useState(false);
  const [txnModal, setTxnModal] = useState<{ lot: Lot; type: TransactionType } | null>(null);

  function reloadAll() {
    stockQ.reload();
    lotsQ.reload();
    txnQ.reload();
    chemQ.reload();
  }

  if (chemQ.loading) return <LoadingState />;
  const chem = chemQ.data;
  if (!chem)
    return (
      <Card>
        <EmptyState title="Không tìm thấy hóa chất" />
      </Card>
    );

  const compatibleUnits = (unitsQ.data ?? []).filter((u) => u.group === chem.measurement_group);

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/chemicals')}
        className="flex w-fit items-center gap-1.5 text-sm text-stem hover:text-ink"
      >
        <ArrowLeft size={16} /> Danh mục hóa chất
      </button>

      <PageHeader
        title={chem.name}
        description={`${chem.cas_no ? `CAS ${chem.cas_no} · ` : ''}${MEASUREMENT_GROUP_LABELS[chem.measurement_group]} · đơn vị cơ sở ${chem.base_unit}`}
        icon={<FlaskConical size={20} />}
        actions={
          canTxn ? (
            <Button onClick={() => setCreateLotOpen(true)}>
              <Plus size={16} /> Thêm lô
            </Button>
          ) : undefined
        }
      />

      {/* Stock summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardBody className="pt-5">
            <p className="text-xs text-subink">Tổng tồn</p>
            <p className="text-2xl font-bold text-ink">
              {formatDecimal(chem.total_stock_base)} <span className="text-base font-medium text-subink">{chem.base_unit}</span>
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="pt-5">
            <p className="text-xs text-subink">Số lô</p>
            <p className="text-2xl font-bold text-ink">{chem.lot_count}</p>
          </CardBody>
        </Card>
        {canCost && (
          <Card>
            <CardBody className="pt-5">
              <p className="text-xs text-subink">Giá trị tồn</p>
              <p className="text-2xl font-bold text-ink">
                {formatMoney(stockQ.data?.total_stock_value, stockQ.data?.currency)}
              </p>
            </CardBody>
          </Card>
        )}
      </div>

      {/* Lots */}
      <Card>
        <CardHeader title="Lô hàng" subtitle="Tồn theo từng lô" />
        <CardBody className="p-0">
          {lotsQ.loading ? (
            <LoadingState />
          ) : (lotsQ.data ?? []).length === 0 ? (
            <EmptyState title="Chưa có lô" description="Thêm lô để bắt đầu nhập tồn." />
          ) : (
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b border-hairline bg-plate/80 text-left text-xs uppercase tracking-wide text-stem">
                    <th className="px-4 py-2.5">Số lô</th>
                    <th className="px-4 py-2.5 text-right">Tồn</th>
                    <th className="px-4 py-2.5">HSD</th>
                    <th className="px-4 py-2.5">Kiểm tra lại</th>
                    <th className="px-4 py-2.5">CoA</th>
                    {canCost && <th className="px-4 py-2.5 text-right">Đơn giá</th>}
                    {canCost && <th className="px-4 py-2.5 text-right">Giá trị</th>}
                    {canTxn && <th className="px-4 py-2.5 text-right">Thao tác</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {(lotsQ.data ?? []).map((lot) => (
                    <tr key={lot.id} className="hover:bg-plate/50">
                      <td className="px-4 py-3 font-medium text-ink">{lot.lot_no}</td>
                      <td className="px-4 py-3 text-right">
                        {formatDecimal(lot.qty_base)} {lot.base_unit}
                      </td>
                      <td className="px-4 py-3">{formatDate(lot.expiry_date ?? undefined)}</td>
                      <td className="px-4 py-3">
                        {lot.recheck_result === 'fail' ? (
                          <Badge tone="overdue">Không đạt</Badge>
                        ) : lot.recheck_result === 'pass' ? (
                          <Badge tone="success">Đạt</Badge>
                        ) : (
                          <span className="text-subink">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          {lot.has_coa && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={async () => {
                                try {
                                  await chemApi.downloadLotCoa(lot.id, lot.lot_no);
                                } catch (err) {
                                  toast.error(describeError(err).title);
                                }
                              }}
                              title="Tải CoA của lô"
                            >
                              <FileDown size={14} /> CoA
                            </Button>
                          )}
                          {canTxn && (
                            <label
                              className="inline-flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-xs text-subink hover:bg-paper hover:text-ink"
                              title={lot.has_coa ? 'Thay CoA của lô' : 'Tải lên CoA cho lô'}
                            >
                              <Upload size={14} /> {lot.has_coa ? 'Thay' : 'Tải lên'}
                              <input
                                type="file"
                                className="hidden"
                                accept=".pdf,.png,.jpg,.jpeg,.xlsx"
                                onChange={async (e) => {
                                  const f = e.target.files?.[0];
                                  e.target.value = '';
                                  if (!f) return;
                                  try {
                                    await chemApi.uploadLotCoa(lot.id, f);
                                    toast.success('Đã tải lên CoA');
                                    reloadAll();
                                  } catch (err) {
                                    toast.error(describeError(err).title);
                                  }
                                }}
                              />
                            </label>
                          )}
                          {!lot.has_coa && !canTxn && <span className="text-subink">—</span>}
                        </div>
                      </td>
                      {canCost && <td className="px-4 py-3 text-right">{formatMoney(lot.unit_price, lot.currency)}</td>}
                      {canCost && <td className="px-4 py-3 text-right">{formatMoney(lot.stock_value, lot.currency)}</td>}
                      {canTxn && (
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1.5">
                            <Button size="sm" variant="ghost" onClick={() => setTxnModal({ lot, type: 'in' })} title="Nhập">
                              <ArrowDownToLine size={14} />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setTxnModal({ lot, type: 'out' })} title="Xuất">
                              <ArrowUpFromLine size={14} />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setTxnModal({ lot, type: 'adjust' })} title="Điều chỉnh">
                              <Scale size={14} />
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Transactions */}
      <Card>
        <CardHeader title="Lịch sử giao dịch" subtitle="Nhập / xuất / điều chỉnh (bất biến)" />
        <CardBody className="p-0">
          {txnQ.loading ? (
            <LoadingState />
          ) : (txnQ.data?.data ?? []).length === 0 ? (
            <EmptyState title="Chưa có giao dịch" />
          ) : (
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-hairline bg-plate/80 text-left text-xs uppercase tracking-wide text-stem">
                    <th className="px-4 py-2.5">Thời gian</th>
                    <th className="px-4 py-2.5">Loại</th>
                    <th className="px-4 py-2.5">Lô</th>
                    <th className="px-4 py-2.5 text-right">Số lượng</th>
                    <th className="px-4 py-2.5 text-right">Tồn sau</th>
                    <th className="px-4 py-2.5">Mẫu</th>
                    <th className="px-4 py-2.5">Người</th>
                    {canCost && <th className="px-4 py-2.5 text-right">Giá trị</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {(txnQ.data?.data ?? []).map((t) => (
                    <tr key={t.id} className="hover:bg-plate/50">
                      <td className="px-4 py-3 whitespace-nowrap text-subink">{formatDateTime(t.at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <TxnTypeBadge type={t.type} />
                          {t.warning_override && <Badge tone="overdue">cảnh báo</Badge>}
                        </div>
                      </td>
                      <td className="px-4 py-3">{t.lot_no}</td>
                      <td className="px-4 py-3 text-right">
                        {formatDecimal(t.qty_input, 4)} {t.input_unit}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {formatDecimal(t.balance_after)} {t.base_unit}
                      </td>
                      <td className="px-4 py-3">{t.ref_sample_code ?? '—'}</td>
                      <td className="px-4 py-3">{t.by_user_name}</td>
                      {canCost && <td className="px-4 py-3 text-right">{formatMoney(t.line_value, t.currency)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* MSDS / tài liệu an toàn ở cấp hóa chất (CoA đính kèm theo từng lô ở bảng trên) */}
      <Card>
        <CardHeader
          title="Tài liệu an toàn (MSDS)"
          subtitle="Bảng dữ liệu an toàn (MSDS) và tài liệu chung áp dụng cho hóa chất. CoA (phiếu kiểm nghiệm) đính kèm theo từng lô ở bảng phía trên."
        />
        <CardBody>
          <AttachmentPanel
            owner="chemical"
            ownerId={id}
            canUpload={canTxn}
            uploadHint="PDF, PNG, JPG, XLSX — MSDS / tài liệu an toàn của hóa chất"
          />
        </CardBody>
      </Card>

      {createLotOpen && (
        <CreateLotModal
          chemicalId={id}
          units={compatibleUnits}
          canCost={canCost}
          onClose={() => setCreateLotOpen(false)}
          onDone={() => {
            setCreateLotOpen(false);
            reloadAll();
            toast.success('Đã thêm lô');
          }}
        />
      )}
      {txnModal && (
        <TransactionModal
          lot={txnModal.lot}
          type={txnModal.type}
          chemicalId={id}
          units={compatibleUnits}
          canCost={canCost}
          onClose={() => setTxnModal(null)}
          onDone={() => {
            setTxnModal(null);
            reloadAll();
            toast.success('Đã ghi giao dịch');
          }}
        />
      )}
    </div>
  );
}

function CreateLotModal({
  chemicalId,
  units,
  canCost,
  onClose,
  onDone,
}: {
  chemicalId: string;
  units: Unit[];
  canCost: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [lotNo, setLotNo] = useState('');
  const [expiry, setExpiry] = useState('');
  const [recheck, setRecheck] = useState('');
  const [withIntake, setWithIntake] = useState(true);
  const [qty, setQty] = useState('');
  const [unit, setUnit] = useState(units[0]?.code ?? '');
  const [price, setPrice] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!lotNo.trim()) return toast.error('Nhập số lô');
    if (withIntake && (!qty || !unit)) return toast.error('Nhập số lượng và đơn vị nhập ban đầu');
    setSubmitting(true);
    try {
      await chemApi.createLot(chemicalId, {
        lot_no: lotNo.trim(),
        expiry_date: expiry || null,
        recheck_date: recheck || null,
        initial_intake: withIntake
          ? { qty_input: qty, input_unit: unit, unit_price: canCost && price ? price : null }
          : null,
      });
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
      title="Thêm lô hàng"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo lô
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Số lô" required className="sm:col-span-2">
          <Input value={lotNo} onChange={(e) => setLotNo(e.target.value)} placeholder="L2026-001" />
        </Field>
        <Field label="Hạn sử dụng">
          <Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
        </Field>
        <Field label="Ngày kiểm tra lại">
          <Input type="date" value={recheck} onChange={(e) => setRecheck(e.target.value)} />
        </Field>
        <label className="sm:col-span-2 flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={withIntake} onChange={(e) => setWithIntake(e.target.checked)} />
          Nhập tồn ban đầu cho lô
        </label>
        {withIntake && (
          <>
            <Field label="Số lượng nhập" required>
              <Input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" placeholder="vd: 500" />
            </Field>
            <Field label="Đơn vị nhập" required>
              <Select value={unit} onChange={(e) => setUnit(e.target.value)}>
                {units.map((u) => (
                  <option key={u.code} value={u.code}>
                    {u.label} ({u.code})
                  </option>
                ))}
              </Select>
            </Field>
            {canCost && (
              <Field label="Đơn giá (theo đơn vị nhập)" className="sm:col-span-2">
                <Input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" placeholder="vd: 1200" />
              </Field>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function TransactionModal({
  lot,
  type,
  units,
  canCost,
  onClose,
  onDone,
}: {
  lot: Lot;
  type: TransactionType;
  chemicalId: string;
  units: Unit[];
  canCost: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [qty, setQty] = useState('');
  const [unit, setUnit] = useState(units[0]?.code ?? lot.base_unit);
  const [price, setPrice] = useState('');
  const [refSample, setRefSample] = useState('');
  const [note, setNote] = useState('');
  const [adjustMode, setAdjustMode] = useState<'actual' | 'delta'>('actual');
  const [submitting, setSubmitting] = useState(false);
  const [warnConfirm, setWarnConfirm] = useState<{ message: string; body: CreateTransactionBody } | null>(null);

  const title = useMemo(
    () => ({ in: 'Nhập kho', out: 'Xuất kho', adjust: 'Điều chỉnh tồn' })[type],
    [type],
  );

  function buildBody(confirm = false): CreateTransactionBody {
    const base: CreateTransactionBody = { type, input_unit: unit, note: note || null };
    if (type === 'in') {
      base.qty_input = qty;
      if (canCost && price) base.unit_price = price;
    } else if (type === 'out') {
      base.qty_input = qty;
      base.ref_sample_id = refSample;
      base.confirm_warning = confirm;
    } else {
      if (adjustMode === 'actual') base.actual_qty_input = qty;
      else base.delta_input = qty;
    }
    return base;
  }

  async function doSubmit(body: CreateTransactionBody) {
    setSubmitting(true);
    try {
      await chemApi.createTransaction(lot.id, body);
      onDone();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'WARNING_NEEDS_CONFIRM') {
        setWarnConfirm({ message: err.message, body });
      } else {
        toast.error(describeError(err).title);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function submit() {
    if (type !== 'adjust' && (!qty || !unit)) return toast.error('Nhập số lượng và đơn vị');
    if (type === 'adjust' && !qty) return toast.error('Nhập tồn thực tế / chênh lệch');
    if (type === 'out' && !refSample.trim()) return toast.error('Xuất phải gắn mã/ID mẫu');
    if (type === 'adjust' && !note.trim()) return toast.error('Điều chỉnh cần ghi lý do');
    await doSubmit(buildBody(false));
  }

  return (
    <>
      <Modal
        open={!warnConfirm}
        onClose={onClose}
        title={`${title} — lô ${lot.lot_no}`}
        description={`Tồn hiện tại: ${formatDecimal(lot.qty_base)} ${lot.base_unit}`}
        footer={
          <>
            <Button variant="secondary" onClick={onClose} disabled={submitting}>
              Hủy
            </Button>
            <Button onClick={submit} loading={submitting}>
              Ghi giao dịch
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {type === 'adjust' && (
            <Field label="Kiểu điều chỉnh">
              <Select value={adjustMode} onChange={(e) => setAdjustMode(e.target.value as 'actual' | 'delta')}>
                <option value="actual">Nhập tồn thực tế (server tính chênh)</option>
                <option value="delta">Nhập chênh lệch ± trực tiếp</option>
              </Select>
            </Field>
          )}
          <div className="grid grid-cols-2 gap-4">
            <Field
              label={type === 'adjust' ? (adjustMode === 'actual' ? 'Tồn thực tế' : 'Chênh lệch (±)') : 'Số lượng'}
              required
            >
              <Input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" placeholder="vd: 12.5" />
            </Field>
            <Field label="Đơn vị" required>
              <Select value={unit} onChange={(e) => setUnit(e.target.value)}>
                {units.map((u) => (
                  <option key={u.code} value={u.code}>
                    {u.label} ({u.code})
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {type === 'in' && canCost && (
            <Field label="Đơn giá (theo đơn vị nhập)">
              <Input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" placeholder="vd: 1200" />
            </Field>
          )}
          {type === 'out' && (
            <Field label="Mẫu liên quan" required hint="Bắt buộc — truy vết theo ISO 17025">
              <SamplePicker value={refSample} onChange={setRefSample} />
            </Field>
          )}
          <Field label={type === 'adjust' ? 'Lý do (bắt buộc)' : 'Ghi chú'} required={type === 'adjust'}>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!warnConfirm}
        onClose={() => setWarnConfirm(null)}
        title="Lô có cảnh báo"
        message={
          (warnConfirm?.message ?? 'Lô này không đạt kiểm tra lại hoặc đã quá hạn.') +
          ' Xác nhận để tiếp tục xuất (sẽ ghi nhận cờ cảnh báo).'
        }
        confirmText="Vẫn xuất"
        loading={submitting}
        onConfirm={() => {
          if (warnConfirm) {
            const body = { ...warnConfirm.body, confirm_warning: true };
            setWarnConfirm(null);
            doSubmit(body);
          }
        }}
      />
    </>
  );
}

// Ưu tiên hiển thị mẫu đang xử lý khi xuất hóa chất.
const PICKER_STATUS_PRIORITY: Record<string, number> = {
  testing: 0,
  assigned: 1,
  received: 2,
};

/**
 * Chọn mẫu liên quan khi xuất hóa chất — thay cho nhập UUID thủ công.
 * - Tìm theo sample_code (q), ưu tiên mẫu đang testing/assigned.
 * - Trả về sample.id (UUID) cho ref_sample_id.
 */
function SamplePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);
  const listQ = useAsync(
    () => samplesApi.listSamples({ q: search.trim() || undefined, limit: 20 }),
    [search],
  );

  const samples = useMemo<SampleListItem[]>(() => {
    const arr = [...(listQ.data?.data ?? [])];
    arr.sort((a, b) => {
      const pa = PICKER_STATUS_PRIORITY[a.status] ?? 9;
      const pb = PICKER_STATUS_PRIORITY[b.status] ?? 9;
      return pa - pb;
    });
    return arr;
  }, [listQ.data]);

  const selected = samples.find((s) => s.id === value);

  return (
    <div className="flex flex-col gap-2">
      {value ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-hairline bg-plate/40 px-3 py-2 text-sm">
          <span className="min-w-0 truncate">
            <span className="font-semibold text-ink">{selected?.sample_code ?? 'Mẫu đã chọn'}</span>
            {selected?.department_name ? (
              <span className="ml-2 text-xs text-subink">{selected.department_name}</span>
            ) : null}
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              onChange('');
              setOpen(true);
            }}
          >
            Đổi mẫu
          </Button>
        </div>
      ) : (
        <>
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v);
              setOpen(true);
            }}
            placeholder="Tìm theo mã mẫu (vd: SP-2026-0001)…"
          />
          {open && (
            <div className="max-h-52 overflow-y-auto rounded-lg border border-hairline scrollbar-thin">
              {listQ.loading ? (
                <div className="px-3 py-4">
                  <LoadingState />
                </div>
              ) : samples.length === 0 ? (
                <p className="px-3 py-3 text-sm text-subink">Không tìm thấy mẫu phù hợp.</p>
              ) : (
                <ul className="divide-y divide-hairline">
                  {samples.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        onClick={() => {
                          onChange(s.id);
                          setOpen(false);
                        }}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-plate"
                      >
                        <span className="min-w-0">
                          <span className="font-medium text-ink">{s.sample_code}</span>
                          <span className="ml-2 text-xs text-subink">{s.department_name}</span>
                        </span>
                        <Badge tone="neutral">
                          {SAMPLE_STATUS_LABELS[s.status] ?? s.status}
                        </Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
