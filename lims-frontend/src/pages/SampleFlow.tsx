import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Inbox, Plus, Download, Send, FileDown, ClipboardEdit, Paperclip, Lock, ShieldCheck, Clock3, ListChecks, PencilLine, Receipt } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDateTime, formatMoney } from '@/lib/format';
import { EmptyState } from '@/components/ui/States';
import { canManageIntake, canUpdateDispatch } from '@/lib/rbac';
import {
  DISPATCH_STATUS_LABELS,
  INFO_REQUEST_STATUS_LABELS,
  INTAKE_STATUS_LABELS,
  TEST_MATRIX_LABELS,
  type CustomerInfoRequest,
  type IntakeStatus,
  type TestMatrix,
  type TestParameter,
  type DispatchStatus,
  type SampleDispatch,
  type SampleIntake,
} from '@/types';
import * as flowApi from '@/api/sampleFlow';
import * as quoApi from '@/api/quotation';
import * as usersApi from '@/api/users';
import { printIntake, printDispatch } from '@/lib/samplePdf';
import {
  IntakeWorkflow, IntakeStatusBadge, PaymentBadge,
} from '@/components/sampleFlow/IntakeWorkflow';

const DISPATCH_TONE: Record<DispatchStatus, BadgeTone> = {
  sent: 'neutral',
  received: 'warning',
  in_progress: 'warning',
  done: 'success',
  returned: 'overdue',
};

export function SampleFlow() {
  const { user } = useAuth();
  const canManage = canManageIntake(user);
  // Tab "Phiếu nhận mẫu": reception/admin thao tác, leader giám sát (đọc).
  // Phòng lab (KTV/trưởng phòng) chỉ thấy inbox "Mẫu chuyển đến phòng".
  const showIntakes = canManage || user?.role === 'leader';
  const [tab, setTab] = useState<'intakes' | 'dispatches' | 'requests'>(showIntakes ? 'intakes' : 'dispatches');
  // m26: Phòng nhận mẫu/quản trị duyệt yêu cầu xem thông tin KH
  const canApproveInfo = user?.role === 'reception' || user?.role === 'admin';

  const isLab = user?.role === 'staff' || user?.role === 'lab_manager';

  // Từ thông báo: ?intake={id} mở thẳng phiếu; ?focus={dispatchId} resolve → phiếu chứa nó.
  const [params] = useSearchParams();
  const [openIntakeId, setOpenIntakeId] = useState<string | null>(params.get('intake'));
  useEffect(() => {
    const intake = params.get('intake');
    if (intake) {
      setOpenIntakeId(intake);
      if (showIntakes) setTab('intakes');
    }
    const focus = params.get('focus');
    if (focus) {
      flowApi
        .getDispatch(focus)
        .then((d) => {
          setOpenIntakeId(d.intake_id);
          if (showIntakes) setTab('intakes');
        })
        .catch(() => {});
    }
  }, [params, showIntakes]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Nhận & Chuyển mẫu"
        description={
          isLab
            ? 'Chỉ tiêu được chuyển đến phòng bạn — cập nhật trạng thái thực hiện'
            : 'Phòng nhận mẫu tiếp nhận, phân chỉ tiêu và chuyển tới phòng lab'
        }
        icon={<Inbox size={20} />}
      />
      {showIntakes ? (
        <>
          {/* Dưới sm: cuộn ngang 1 hàng thay vì wrap thành nhiều dòng chiếm chỗ */}
          <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 no-scrollbar sm:mx-0 sm:overflow-visible sm:px-0 sm:pb-0">
            <Button className="shrink-0" variant={tab === 'intakes' ? 'primary' : 'secondary'} onClick={() => setTab('intakes')}>
              Phiếu nhận mẫu
            </Button>
            <Button className="shrink-0" variant={tab === 'dispatches' ? 'primary' : 'secondary'} onClick={() => setTab('dispatches')}>
              Mẫu chuyển đến phòng
            </Button>
            {canApproveInfo && (
              <Button variant={tab === 'requests' ? 'primary' : 'secondary'} onClick={() => setTab('requests')}>
                <ShieldCheck size={15} /> Yêu cầu xem thông tin KH
              </Button>
            )}
          </div>
          {tab === 'intakes' ? (
            <IntakesTab canManage={canManage} openId={openIntakeId} />
          ) : tab === 'requests' ? (
            <InfoRequestsTab />
          ) : (
            <DispatchesTab />
          )}
        </>
      ) : (
        <DispatchesTab />
      )}
    </div>
  );
}

// ===== Tab Phiếu nhận =====
function IntakesTab({ canManage, openId }: { canManage: boolean; openId?: string | null }) {
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [statusFilter, setStatusFilter] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(openId ?? null);
  useEffect(() => {
    if (openId) setDetailId(openId);
  }, [openId]);

  const { data, loading, reload } = useAsync(
    () => flowApi.listIntakes({ q: dq || undefined, status: statusFilter || undefined, limit: 100 }),
    [dq, statusFilter],
  );

  const columns: Column<SampleIntake>[] = [
    { key: 'code', header: 'Mã phiếu', render: (r) => <span className="font-semibold text-ink">{r.code}</span> },
    { key: 'customer', header: 'Khách hàng', render: (r) => r.customer_name },
    { key: 'desc', header: 'Mô tả mẫu', render: (r) => <span className="text-subink">{r.description ?? '—'}</span> },
    {
      key: 'ct', header: 'Chỉ tiêu → Phòng lab',
      render: (r) => {
        const ds = r.dispatches ?? [];
        if (!ds.length) return <span className="text-sm text-subink">Chưa chuyển</span>;
        return (
          <div className="flex flex-col gap-0.5">
            {ds.slice(0, 2).map((d) => (
              <span key={d.id} className="text-xs text-ink">
                {d.chi_tieu} <span className="text-subink">→ {d.target_department_name}</span>
              </span>
            ))}
            {ds.length > 2 && <span className="text-xs text-subink">+{ds.length - 2} chỉ tiêu nữa</span>}
          </div>
        );
      },
    },
    { key: 'status', header: 'Trạng thái', render: (r) => <IntakeStatusBadge status={r.status} /> },
    { key: 'payment', header: 'Thanh toán', render: (r) => <PaymentBadge status={r.payment_status} /> },
    {
      key: 'actions', header: '',
      render: (r) =>
        canManage ? (
          <Button variant="secondary" size="sm" onClick={() => setDetailId(r.id)}>
            <Send size={14} /> Chuyển mẫu
          </Button>
        ) : null,
    },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
        <SearchInput value={q} onChange={setQ} placeholder="Mã phiếu / khách hàng…" className="max-w-xs" />
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full sm:max-w-[190px]">
          <option value="">— Mọi trạng thái —</option>
          {(Object.keys(INTAKE_STATUS_LABELS) as IntakeStatus[]).map((st) => (
            <option key={st} value={st}>{INTAKE_STATUS_LABELS[st]}</option>
          ))}
        </Select>
        {canManage && (
          <Button className="ml-auto" onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Nhận mẫu mới
          </Button>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={data?.data ?? []}
        rowKey={(r) => r.id}
        loading={loading}
        pageSize={12}
        onRowClick={(r) => setDetailId(r.id)}
      />
      {createOpen && (
        <IntakeCreateModal
          onClose={() => setCreateOpen(false)}
          onDone={(it) => { setCreateOpen(false); reload(); setDetailId(it.id); }}
        />
      )}
      {detailId && (
        <IntakeDetailModal
          intakeId={detailId}
          canManage={canManage}
          onClose={() => setDetailId(null)}
          onChanged={reload}
        />
      )}
    </Card>
  );
}

function IntakeCreateModal({ onClose, onDone }: { onClose: () => void; onDone: (intake: SampleIntake) => void }) {
  const toast = useToast();
  const [f, setF] = useState({
    customer_name: '', address: '', tax_code: '', contact_person: '', phone: '', email: '',
    due_date: '', result_language: '', return_method: '', fee_note: '', description: '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((p) => ({ ...p, [k]: e.target.value }));

  async function submit() {
    if (!f.customer_name.trim()) return toast.error('Nhập tên khách hàng');
    setSubmitting(true);
    try {
      const it = await flowApi.createIntake({
        customer_name: f.customer_name.trim(),
        address: f.address || null,
        tax_code: f.tax_code || null,
        contact_person: f.contact_person || null,
        phone: f.phone || null,
        email: f.email || null,
        due_date: f.due_date || null,
        result_language: f.result_language || null,
        return_method: f.return_method || null,
        fee_note: f.fee_note || null,
        description: f.description || null,
      });
      if (file) await flowApi.uploadIntakeFile('sample_intake', it.id, file);
      toast.success(`Đã tạo phiếu ${it.code} — phân chỉ tiêu để chuyển lab`);
      onDone(it);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open onClose={onClose} title="Nhận mẫu mới (BM 7.1.01)" size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button>
          <Button onClick={submit} loading={submitting}>Lưu phiếu</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Tên khách hàng / đơn vị" required>
          <Input value={f.customer_name} onChange={set('customer_name')} />
        </Field>
        <Field label="Địa chỉ">
          <Input value={f.address} onChange={set('address')} />
        </Field>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <Field label="Mã số thuế"><Input value={f.tax_code} onChange={set('tax_code')} /></Field>
          <Field label="Người liên hệ"><Input value={f.contact_person} onChange={set('contact_person')} /></Field>
          <Field label="Điện thoại"><Input value={f.phone} onChange={set('phone')} /></Field>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Mail"><Input value={f.email} onChange={set('email')} /></Field>
          <Field label="Ngày hẹn trả kết quả"><Input value={f.due_date} onChange={set('due_date')} placeholder="dd/mm/yyyy" /></Field>
        </div>
        <Field label="Mô tả mẫu">
          <Textarea value={f.description} onChange={set('description')} />
        </Field>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <Field label="Phiếu kết quả">
            <Select value={f.result_language} onChange={set('result_language')}>
              <option value="">—</option>
              <option value="vi">Tiếng Việt</option>
              <option value="en">Tiếng Anh</option>
            </Select>
          </Field>
          <Field label="Trả kết quả">
            <Select value={f.return_method} onChange={set('return_method')}>
              <option value="">—</option>
              <option value="direct">Trả trực tiếp</option>
              <option value="mail">Thư</option>
              <option value="email">E-mail</option>
            </Select>
          </Field>
          <Field label="Lệ phí / ứng trước"><Input value={f.fee_note} onChange={set('fee_note')} /></Field>
        </div>
        <Field label="Phiếu nhận mẫu đã điền (BM 7.1.01)">
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
    </Modal>
  );
}

function IntakeDetailModal({
  intakeId, canManage, onClose, onChanged,
}: {
  intakeId: string; canManage: boolean; onClose: () => void; onChanged: () => void;
}) {
  const toast = useToast();
  const [quoting, setQuoting] = useState(false);
  const [editDispatch, setEditDispatch] = useState<SampleDispatch | null>(null);
  const { data: intake, reload } = useAsync(() => flowApi.getIntake(intakeId), [intakeId]);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);
  const labs = (depts?.data ?? []).filter((d) => d.kind === 'lab');

  const [chiTieu, setChiTieu] = useState('');
  const [labId, setLabId] = useState('');
  const [sending, setSending] = useState(false);
  // m27: chọn chỉ tiêu từ DANH MỤC (mặc định) hoặc nhập TỰ DO
  const [mode, setMode] = useState<'catalog' | 'free'>('catalog');
  // BM 7.1.02: Loại/Tên mẫu + Số lượng áp cho các chỉ tiêu sắp chuyển
  const [sampleName, setSampleName] = useState('');
  const [qty, setQty] = useState('1');
  const [paramQuery, setParamQuery] = useState('');
  const [paramMatrix, setParamMatrix] = useState('');
  const [picked, setPicked] = useState<TestParameter[]>([]);
  const totalPicked = picked.reduce((sum, p) => sum + Number(p.unit_price ?? 0), 0);
  const paramsQ = useAsync(
    () =>
      flowApi.listTestParameters({
        q: paramQuery || undefined,
        matrix: paramMatrix || undefined,
        is_active: true,
        limit: 30,
      }),
    [paramQuery, paramMatrix],
  );

  /** Thêm/bớt chỉ tiêu trong "giỏ" đã chọn; tự điền phòng lab mặc định của chỉ tiêu đầu tiên. */
  function togglePick(p: TestParameter) {
    setPicked((prev) => {
      if (prev.some((x) => x.id === p.id)) return prev.filter((x) => x.id !== p.id);
      if (prev.length === 0 && p.department_id) setLabId(p.department_id);
      return [...prev, p];
    });
  }

  async function sendDispatch() {
    if (mode === 'catalog' && picked.length === 0) return toast.error('Chọn ít nhất 1 chỉ tiêu từ danh mục');
    if (mode === 'free' && !chiTieu.trim()) return toast.error('Nhập chỉ tiêu');
    if (!labId) return toast.error('Chọn phòng lab');
    setSending(true);
    try {
      if (mode === 'catalog') {
        // Mỗi chỉ tiêu → 1 phiếu chuyển; phòng lab riêng của chỉ tiêu (nếu có), không thì phòng đã chọn.
        await flowApi.addDispatchesBatch(
          intakeId,
          picked.map((p) => ({
            test_parameter_id: p.id,
            target_department_id: p.department_id || labId,
            sample_name: sampleName.trim() || null,
            quantity: Number(qty) || 1,
          })),
        );
        toast.success(
          `Đã chuyển ${picked.length} chỉ tiêu`,
          'Phòng lab liên quan sẽ nhận thông báo.',
        );
      } else {
        await flowApi.addDispatch(intakeId, {
          chi_tieu: chiTieu.trim(),
          target_department_id: labId,
          sample_name: sampleName.trim() || null,
          quantity: Number(qty) || 1,
        });
        toast.success('Đã chuyển mẫu — phòng lab sẽ nhận thông báo');
      }
      setChiTieu('');
      setPicked([]);
      setParamQuery('');
      setLabId('');
      reload();
      onChanged();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSending(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={intake ? `Phiếu ${intake.code}` : 'Phiếu nhận mẫu'} size="xl">
      {editDispatch && (
        <DispatchEditModal
          dispatch={editDispatch}
          canEdit={canManage}
          onClose={() => setEditDispatch(null)}
          onSaved={() => { setEditDispatch(null); reload(); onChanged(); }}
        />
      )}
      {!intake ? (
        <div className="p-6 text-center text-subink">Đang tải…</div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => printIntake(intake)}>
              <FileDown size={14} /> Xuất phiếu nhận (PDF)
            </Button>
            <Button variant="secondary" size="sm" onClick={() => printDispatch(intake)}>
              <FileDown size={14} /> Xuất phiếu chuyển (PDF)
            </Button>
            {canManage && (
              <Button
                variant="secondary"
                size="sm"
                loading={quoting}
                onClick={async () => {
                  setQuoting(true);
                  try {
                    const q = await quoApi.createQuotationFromIntake(intake.id);
                    toast.success(`Đã lập báo giá ${q.code}`, 'Mở menu "Báo giá" để xem, gửi khách và xuất Excel.');
                    reload();
                    onChanged();
                  } catch (err) {
                    const e = describeError(err);
                    toast.error(e.title, e.description);
                  } finally {
                    setQuoting(false);
                  }
                }}
              >
                <Receipt size={14} /> Tạo báo giá từ phiếu
              </Button>
            )}
          </div>
          {/* m26: PII khách hàng bị ẩn với khối lab — phải xin Phòng nhận mẫu duyệt */}
          {intake.customer_info_masked ? (
            <CustomerInfoLocked intake={intake} onRequested={onChanged} />
          ) : (
            <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2 gap-y-2 text-sm">
              <div><span className="text-subink">Khách hàng:</span> <span className="font-medium text-ink">{intake.customer_name}</span></div>
              <div><span className="text-subink">Mã số thuế:</span> {intake.tax_code ?? '—'}</div>
              <div className="sm:col-span-2"><span className="text-subink">Địa chỉ:</span> {intake.address ?? '—'}</div>
              <div><span className="text-subink">Người liên hệ:</span> {intake.contact_person ?? '—'}</div>
              <div><span className="text-subink">Điện thoại:</span> {intake.phone ?? '—'}</div>
              <div><span className="text-subink">Mail:</span> {intake.email ?? '—'}</div>
            </div>
          )}
          {/* m28: tiến trình phiếu + thanh toán + cảnh báo */}
          <IntakeWorkflow intake={intake} canManage={canManage} onChanged={() => { reload(); onChanged(); }} />

          <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2 gap-y-2 text-sm">
            <div><span className="text-subink">Ngày hẹn trả KQ:</span> {intake.due_date ?? '—'}</div>
            <div className="sm:col-span-2"><span className="text-subink">Mô tả mẫu:</span> {intake.description ?? '—'}</div>
          </div>

          {intake.files.length > 0 && (
            <div>
              <div className="mb-1 text-sm font-semibold text-ink">Tệp đính kèm</div>
              {intake.files.map((f) => (
                <button key={f.id} className="flex items-center gap-1 text-sm text-blueberry hover:underline"
                  onClick={() => flowApi.openFile(f.id).catch((e) => toast.error(describeError(e).title))}>
                  <Download size={13} /> {f.file_name}
                </button>
              ))}
            </div>
          )}

          {/* Chỉ tiêu đã chuyển */}
          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-ink">
                Chỉ tiêu đã chuyển ({intake.dispatches?.length ?? 0}) — BM 7.1.02
              </span>
              <span className="text-xs text-subink">
                Tổng số mẫu: {(intake.dispatches ?? []).reduce((n, d) => n + (d.quantity ?? 1), 0)}
              </span>
            </div>
            {/* Bảng đủ 8 cột theo BM 7.1.02 */}
            <div className="overflow-x-auto rounded-lg border border-hairline scrollbar-thin">
              <table className="w-full min-w-[880px] border-collapse text-xs table-sticky-1">
                <thead className="bg-plate">
                  <tr className="text-left text-subink">
                    <th className="w-8 px-2 py-1.5 text-center">Stt</th>
                    <th className="px-2 py-1.5">Loại/Tên mẫu</th>
                    <th className="px-2 py-1.5">Chỉ tiêu thử nghiệm</th>
                    <th className="w-14 px-2 py-1.5 text-center">SL</th>
                    <th className="w-16 px-2 py-1.5">Đơn vị</th>
                    <th className="px-2 py-1.5">Kết quả</th>
                    <th className="px-2 py-1.5">Phương pháp</th>
                    <th className="px-2 py-1.5">Cán bộ PT</th>
                    <th className="px-2 py-1.5">Ghi chú</th>
                    <th className="px-2 py-1.5">Phòng lab / Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {(intake.dispatches ?? []).map((d, i) => (
                    <tr
                      key={d.id}
                      className="cursor-pointer align-top transition-colors hover:bg-plate"
                      onClick={() => setEditDispatch(d)}
                      title="Bấm để xem chi tiết & sửa"
                    >
                      <td className="px-2 py-1.5 text-center text-subink">{i + 1}</td>
                      <td className="px-2 py-1.5 text-ink">{d.sample_name ?? intake.description ?? '—'}</td>
                      <td className="px-2 py-1.5 font-medium text-ink">
                        {d.chi_tieu}
                        {d.files.length > 0 && <Paperclip size={11} className="ml-1 inline text-subink" />}
                      </td>
                      <td className="px-2 py-1.5 text-center text-ink">{d.quantity ?? 1}</td>
                      <td className="px-2 py-1.5 text-subink">{d.don_vi ?? '—'}</td>
                      <td className="px-2 py-1.5 font-medium text-ink">{d.ket_qua ?? '—'}</td>
                      <td className="px-2 py-1.5 text-subink">{d.phuong_phap ?? '—'}</td>
                      <td className="px-2 py-1.5 text-subink">{d.can_bo ?? '—'}</td>
                      <td className="px-2 py-1.5 text-subink">{d.note ?? '—'}</td>
                      <td className="px-2 py-1.5">
                        <div className="flex flex-col gap-1">
                          <span className="text-subink">{d.target_department_name}</span>
                          <Badge tone={DISPATCH_TONE[d.status]}>{DISPATCH_STATUS_LABELS[d.status]}</Badge>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {(intake.dispatches?.length ?? 0) === 0 && (
                    <tr>
                      <td colSpan={10} className="px-2 py-4 text-center text-subink">
                        Chưa chuyển chỉ tiêu nào.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Thêm chỉ tiêu → chọn phòng lab */}
          {canManage && (
            <div className="rounded-lg bg-plate p-3">
              <div className="mb-2 text-sm font-semibold text-ink">Phân chỉ tiêu & chuyển phòng lab</div>
              <div className="flex flex-col gap-3">
                {/* BM 7.1.02: Loại/Tên mẫu + Số lượng */}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                  <Field label="Loại / Tên mẫu" className="md:col-span-2" hint="Theo BM 7.1.02">
                    <Input
                      value={sampleName}
                      onChange={(e) => setSampleName(e.target.value)}
                      placeholder="VD: Hạt ớt, Mẫu nước giếng…"
                    />
                  </Field>
                  <Field label="Số lượng">
                    <Input type="number" min={1} value={qty} onChange={(e) => setQty(e.target.value)} />
                  </Field>
                </div>

                {/* m27: chọn chỉ tiêu từ danh mục (có phương pháp + đơn giá) hoặc nhập tự do */}
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={mode === 'catalog' ? 'primary' : 'secondary'}
                    onClick={() => setMode('catalog')}
                  >
                    <ListChecks size={14} /> Chọn từ danh mục
                  </Button>
                  <Button
                    size="sm"
                    variant={mode === 'free' ? 'primary' : 'secondary'}
                    onClick={() => setMode('free')}
                  >
                    <PencilLine size={14} /> Nhập tự do
                  </Button>
                </div>

                {mode === 'free' ? (
                  <Field label="Chỉ tiêu (nhập tự do)" hint="Dùng khi chỉ tiêu chưa có trong danh mục">
                    <Textarea
                      value={chiTieu}
                      onChange={(e) => setChiTieu(e.target.value)}
                      placeholder="VD: pH, độ đục, kim loại nặng…"
                    />
                  </Field>
                ) : (
                  <div className="flex flex-col gap-2">
                    {/* Giỏ chỉ tiêu đã chọn */}
                    {picked.length > 0 && (
                      <div className="rounded-lg border border-blueberry/30 bg-blueberry/5 p-2.5">
                        <div className="mb-1.5 flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-ink">
                            Đã chọn {picked.length} chỉ tiêu
                            {totalPicked > 0 && (
                              <span className="ml-1.5 font-normal text-subink">
                                · Tổng: <strong className="text-ink">{formatMoney(String(totalPicked))}</strong>
                              </span>
                            )}
                          </span>
                          <button
                            onClick={() => setPicked([])}
                            className="text-xs text-overdue hover:underline"
                          >
                            Bỏ hết
                          </button>
                        </div>
                        <ul className="flex flex-wrap gap-1.5">
                          {picked.map((p) => (
                            <li
                              key={p.id}
                              className="flex max-w-full items-center gap-1.5 rounded-md bg-surface px-2 py-1 text-xs ring-1 ring-hairline"
                            >
                              <span className="truncate font-medium text-ink">{p.name}</span>
                              {p.department_name && (
                                <span className="shrink-0 text-subink">· {p.department_name}</span>
                              )}
                              <button
                                onClick={() => togglePick(p)}
                                title="Bỏ chỉ tiêu này"
                                className="shrink-0 text-stem hover:text-overdue"
                              >
                                ✕
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Bộ lọc + danh sách chọn (bấm để thêm/bớt, danh sách vẫn mở) */}
                    <div className="flex flex-wrap gap-2">
                      <SearchInput
                        value={paramQuery}
                        onChange={setParamQuery}
                        placeholder="Tìm chỉ tiêu / phương pháp…"
                        className="w-full sm:min-w-[220px] sm:flex-1"
                      />
                      <Select
                        value={paramMatrix}
                        onChange={(e) => setParamMatrix(e.target.value)}
                        className="w-full sm:max-w-[210px]"
                      >
                        <option value="">— Mọi nền mẫu —</option>
                        {(Object.keys(TEST_MATRIX_LABELS) as TestMatrix[]).map((m) => (
                          <option key={m} value={m}>{TEST_MATRIX_LABELS[m]}</option>
                        ))}
                      </Select>
                    </div>
                    <div className="max-h-56 overflow-y-auto rounded-lg border border-hairline scrollbar-thin">
                      {paramsQ.loading ? (
                        <p className="p-3 text-sm text-subink">Đang tải…</p>
                      ) : (paramsQ.data?.data ?? []).length === 0 ? (
                        <p className="p-3 text-sm text-subink">
                          Không tìm thấy chỉ tiêu. Bấm "Nhập tự do" nếu chỉ tiêu chưa có trong danh mục.
                        </p>
                      ) : (
                        <ul className="divide-y divide-hairline">
                          {(paramsQ.data?.data ?? []).map((p) => {
                            const on = picked.some((x) => x.id === p.id);
                            return (
                              <li key={p.id}>
                                <button
                                  onClick={() => togglePick(p)}
                                  className={
                                    'flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-plate ' +
                                    (on ? 'bg-blueberry/5' : '')
                                  }
                                >
                                  <input
                                    type="checkbox"
                                    checked={on}
                                    readOnly
                                    tabIndex={-1}
                                    className="mt-1 shrink-0"
                                  />
                                  <span className="min-w-0 flex-1">
                                    <span className="block truncate text-sm font-medium text-ink">{p.name}</span>
                                    <span className="block truncate text-xs text-subink">
                                      {p.matrix_label}{p.method ? ` · ${p.method}` : ''}
                                      {p.department_name ? ` · ${p.department_name}` : ''}
                                    </span>
                                  </span>
                                  <span className="shrink-0 text-xs font-medium text-ink">
                                    {p.unit_price ? formatMoney(p.unit_price) : '—'}
                                  </span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                <Field
                  label="Phòng lab tiếp nhận"
                  hint={
                    mode === 'catalog'
                      ? 'Chỉ tiêu đã gán phòng sẽ tự chuyển tới phòng đó; phòng chọn ở đây dùng cho chỉ tiêu chưa gán.'
                      : undefined
                  }
                >
                  <Select value={labId} onChange={(e) => setLabId(e.target.value)}>
                    <option value="">— Chọn phòng —</option>
                    {labs.map((l) => (
                      <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                  </Select>
                </Field>
                <div>
                  <Button onClick={sendDispatch} loading={sending}>
                    <Send size={15} />
                    {mode === 'catalog' && picked.length > 1 ? `Chuyển ${picked.length} chỉ tiêu` : 'Chuyển mẫu'}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// ===== Tab Mẫu chuyển đến (inbox lab) =====
function DispatchesTab() {
  const { user } = useAuth();
  const toast = useToast();
  const canUpdate = canUpdateDispatch(user);
  const [editing, setEditing] = useState<SampleDispatch | null>(null);
  const [detail, setDetail] = useState<SampleDispatch | null>(null);
  const { data, loading, reload } = useAsync(() => flowApi.listDispatches({ limit: 100 }), []);

  async function changeStatus(d: SampleDispatch, status: DispatchStatus) {
    try {
      await flowApi.updateDispatch(d.id, { status });
      toast.success('Đã cập nhật trạng thái — phòng nhận mẫu sẽ được thông báo');
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    }
  }

  const columns: Column<SampleDispatch>[] = [
    { key: 'code', header: 'Mã phiếu', render: (d) => <span className="font-semibold text-ink">{d.intake_code}</span> },
    { key: 'ct', header: 'Chỉ tiêu', render: (d) => <span className="text-ink">{d.chi_tieu}</span> },
    { key: 'dept', header: 'Phòng lab', render: (d) => d.target_department_name ?? '—' },
    { key: 'kq', header: 'Kết quả', render: (d) => <span className="text-subink">{d.ket_qua ?? '—'}</span> },
    {
      key: 'files', header: 'Đính kèm',
      render: (d) =>
        d.files.length > 0 ? (
          <div className="flex flex-col gap-0.5" onClick={(e) => e.stopPropagation()}>
            {d.files.map((f) => (
              <button key={f.id} className="flex items-center gap-1 text-xs text-blueberry hover:underline"
                onClick={() => flowApi.openFile(f.id).catch((e) => toast.error(describeError(e).title))}>
                <Paperclip size={12} /> {f.file_name}
              </button>
            ))}
          </div>
        ) : (
          <span className="text-sm text-subink">—</span>
        ),
    },
    {
      key: 'status', header: 'Trạng thái',
      render: (d) =>
        canUpdate ? (
          <div onClick={(e) => e.stopPropagation()}>
            <Select value={d.status} onChange={(e) => changeStatus(d, e.target.value as DispatchStatus)} className="w-full sm:w-auto sm:min-w-[150px]">
              {(Object.keys(DISPATCH_STATUS_LABELS) as DispatchStatus[]).map((s) => (
                <option key={s} value={s}>{DISPATCH_STATUS_LABELS[s]}</option>
              ))}
            </Select>
          </div>
        ) : (
          <Badge tone={DISPATCH_TONE[d.status]}>{DISPATCH_STATUS_LABELS[d.status]}</Badge>
        ),
    },
    {
      key: 'actions', header: '',
      render: (d) =>
        canUpdate ? (
          <div onClick={(e) => e.stopPropagation()}>
            <Button variant="secondary" size="sm" onClick={() => setEditing(d)}>
              <ClipboardEdit size={14} /> Nhập kết quả
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <Card>
      <DataTable
        columns={columns}
        rows={data?.data ?? []}
        rowKey={(d) => d.id}
        loading={loading}
        pageSize={12}
        onRowClick={(d) => setDetail(d)}
      />
      {detail && (
        <DispatchDetailModal
          dispatch={detail}
          canUpdate={canUpdate}
          onClose={() => setDetail(null)}
          onEnterResult={(d) => { setDetail(null); setEditing(d); }}
          onChanged={reload}
        />
      )}
      {editing && (
        <DispatchResultModal
          dispatch={editing}
          onClose={() => setEditing(null)}
          onDone={() => { setEditing(null); reload(); toast.success('Đã lưu kết quả'); }}
        />
      )}
    </Card>
  );
}

function DispatchResultModal({
  dispatch, onClose, onDone,
}: {
  dispatch: SampleDispatch; onClose: () => void; onDone: () => void;
}) {
  const toast = useToast();
  const [v, setV] = useState({
    don_vi: dispatch.don_vi ?? '', phuong_phap: dispatch.phuong_phap ?? '',
    ket_qua: dispatch.ket_qua ?? '', can_bo: dispatch.can_bo ?? '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((p) => ({ ...p, [k]: e.target.value }));

  async function save() {
    setSaving(true);
    try {
      await flowApi.updateDispatch(dispatch.id, {
        don_vi: v.don_vi || null, phuong_phap: v.phuong_phap || null,
        ket_qua: v.ket_qua || null, can_bo: v.can_bo || null,
      });
      if (file) await flowApi.uploadIntakeFile('sample_dispatch', dispatch.id, file);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open onClose={onClose} title={`Kết quả — ${dispatch.chi_tieu}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>Hủy</Button>
          <Button onClick={save} loading={saving}>Lưu kết quả</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Đơn vị"><Input value={v.don_vi} onChange={set('don_vi')} /></Field>
          <Field label="Cán bộ phân tích"><Input value={v.can_bo} onChange={set('can_bo')} /></Field>
        </div>
        <Field label="Phương pháp thử"><Textarea value={v.phuong_phap} onChange={set('phuong_phap')} /></Field>
        <Field label="Kết quả"><Textarea value={v.ket_qua} onChange={set('ket_qua')} /></Field>

        {dispatch.files.length > 0 && (
          <div>
            <div className="mb-1 text-sm font-semibold text-ink">Tệp đính kèm</div>
            <div className="flex flex-col gap-1">
              {dispatch.files.map((f) => (
                <button key={f.id} className="flex items-center gap-1 text-sm text-blueberry hover:underline"
                  onClick={() => flowApi.openFile(f.id).catch((e) => toast.error(describeError(e).title))}>
                  <Download size={13} /> {f.file_name}
                </button>
              ))}
            </div>
          </div>
        )}
        <Field label="Đính kèm kết quả (báo cáo, ảnh, số liệu thô…)">
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
    </Modal>
  );
}

/**
 * m26 — Khối "thông tin khách hàng đã ẩn" cho phòng lab.
 * Lab chỉ nhận diện mẫu qua MÃ PHIẾU; muốn xem PII phải gửi yêu cầu → Phòng nhận mẫu duyệt.
 */
function CustomerInfoLocked({ intake, onRequested }: { intake: SampleIntake; onRequested: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [sending, setSending] = useState(false);
  const pending = intake.customer_info_request_status === 'pending';

  async function send() {
    setSending(true);
    try {
      await flowApi.createInfoRequest(intake.id, reason.trim() || undefined);
      toast.success('Đã gửi yêu cầu', 'Phòng nhận mẫu sẽ xem xét và phản hồi.');
      setOpen(false);
      setReason('');
      onRequested();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <div className="rounded-xl border border-hairline bg-plate p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-stem/10 text-stem">
              <Lock size={16} />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">Thông tin khách hàng đã được ẩn</p>
              <p className="mt-0.5 text-xs text-subink">
                Tên khách hàng, mã số thuế, địa chỉ, người liên hệ, điện thoại, email chỉ hiển thị sau khi
                Phòng nhận mẫu chấp thuận. Mẫu được nhận diện qua mã phiếu <strong className="text-ink">{intake.code}</strong>.
              </p>
            </div>
          </div>
          {pending ? (
            <Badge tone="warning">
              <Clock3 size={12} /> Đang chờ duyệt
            </Badge>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
              <ShieldCheck size={14} /> Yêu cầu xem thông tin
            </Button>
          )}
        </div>
      </div>

      {open && (
        <Modal
          open
          onClose={() => setOpen(false)}
          title="Yêu cầu xem thông tin khách hàng"
          description={`Phiếu ${intake.code} — yêu cầu sẽ được gửi tới Phòng nhận mẫu`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setOpen(false)}>Hủy</Button>
              <Button onClick={send} loading={sending}>Gửi yêu cầu</Button>
            </>
          }
        >
          <Field label="Lý do cần xem thông tin" hint="Giúp Phòng nhận mẫu duyệt nhanh hơn (không bắt buộc)">
            <Textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="VD: cần liên hệ khách để xác nhận điều kiện bảo quản mẫu…"
            />
          </Field>
        </Modal>
      )}
    </>
  );
}

/**
 * m26 — Phòng nhận mẫu duyệt/từ chối yêu cầu xem thông tin khách hàng.
 * Duyệt xong: phòng của người xin được xem PII của phiếu đó (vĩnh viễn).
 */
function InfoRequestsTab() {
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState('pending');
  const { data, loading, reload } = useAsync(
    () => flowApi.listInfoRequests({ status: statusFilter || undefined, limit: 100 }),
    [statusFilter],
  );
  const [busyId, setBusyId] = useState<string | null>(null);

  async function decide(r: CustomerInfoRequest, approve: boolean) {
    setBusyId(r.id);
    try {
      if (approve) {
        await flowApi.approveInfoRequest(r.id);
        toast.success('Đã duyệt', `${r.department_name ?? 'Phòng lab'} có thể xem thông tin khách hàng của phiếu ${r.intake_code ?? ''}.`);
      } else {
        await flowApi.rejectInfoRequest(r.id);
        toast.success('Đã từ chối yêu cầu');
      }
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusyId(null);
    }
  }

  const columns: Column<CustomerInfoRequest>[] = [
    { key: 'code', header: 'Phiếu', render: (r) => <span className="font-semibold text-ink">{r.intake_code ?? '—'}</span> },
    { key: 'requester', header: 'Người yêu cầu', render: (r) => r.requester_name ?? '—' },
    { key: 'dept', header: 'Phòng', render: (r) => r.department_name ?? '—' },
    { key: 'reason', header: 'Lý do', render: (r) => <span className="text-subink">{r.reason ?? '—'}</span> },
    { key: 'at', header: 'Gửi lúc', render: (r) => formatDateTime(r.created_at) },
    {
      key: 'status', header: 'Trạng thái',
      render: (r) => (
        <Badge tone={r.status === 'approved' ? 'success' : r.status === 'rejected' ? 'overdue' : 'warning'}>
          {INFO_REQUEST_STATUS_LABELS[r.status] ?? r.status}
        </Badge>
      ),
    },
    {
      key: 'actions', header: '', align: 'right',
      render: (r) =>
        r.status === 'pending' ? (
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="success" loading={busyId === r.id} onClick={() => decide(r, true)}>
              Duyệt
            </Button>
            <Button size="sm" variant="secondary" loading={busyId === r.id} onClick={() => decide(r, false)}>
              Từ chối
            </Button>
          </div>
        ) : (
          <span className="text-xs text-subink">
            {r.decided_by_name ? `${r.decided_by_name} · ${r.decided_at ? formatDateTime(r.decided_at) : ''}` : '—'}
          </span>
        ),
    },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
        <span className="text-sm text-subink">Trạng thái:</span>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full sm:max-w-[200px]">
          <option value="pending">Chờ duyệt</option>
          <option value="approved">Đã duyệt</option>
          <option value="rejected">Từ chối</option>
          <option value="">Tất cả</option>
        </Select>
      </div>
      <DataTable
        columns={columns}
        rows={data?.data ?? []}
        rowKey={(r) => r.id}
        loading={loading}
        pageSize={12}
        empty={<EmptyState title="Không có yêu cầu" description="Chưa có phòng lab nào xin xem thông tin khách hàng." />}
      />
    </Card>
  );
}

/**
 * Chi tiết 1 chỉ tiêu được chuyển đến phòng lab (click vào dòng trong tab "Mẫu chuyển đến phòng").
 * Hiển thị thông tin phiếu + chỉ tiêu + mốc thời gian + tệp; PII khách hàng vẫn tuân thủ m26.
 */
function DispatchDetailModal({
  dispatch,
  canUpdate,
  onClose,
  onEnterResult,
  onChanged,
}: {
  dispatch: SampleDispatch;
  canUpdate: boolean;
  onClose: () => void;
  onEnterResult: (d: SampleDispatch) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const { data: intake, reload } = useAsync(() => flowApi.getIntake(dispatch.intake_id), [dispatch.intake_id]);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Phiếu ${dispatch.intake_code ?? ''} · ${dispatch.chi_tieu}`}
      description={dispatch.target_department_name ? `Phòng thực hiện: ${dispatch.target_department_name}` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Đóng</Button>
          {canUpdate && (
            <Button onClick={() => onEnterResult(dispatch)}>
              <ClipboardEdit size={14} /> Nhập kết quả
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {/* Thông tin khách hàng — ẩn với khối lab chưa được duyệt (m26) */}
        {intake?.customer_info_masked ? (
          <CustomerInfoLocked intake={intake} onRequested={() => { reload(); onChanged(); }} />
        ) : intake ? (
          <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2 gap-y-2 rounded-xl border border-hairline bg-plate p-4 text-sm">
            <div><span className="text-subink">Khách hàng:</span> <span className="font-medium text-ink">{intake.customer_name}</span></div>
            <div><span className="text-subink">Mã số thuế:</span> {intake.tax_code ?? '—'}</div>
            <div className="sm:col-span-2"><span className="text-subink">Địa chỉ:</span> {intake.address ?? '—'}</div>
            <div><span className="text-subink">Người liên hệ:</span> {intake.contact_person ?? '—'}</div>
            <div><span className="text-subink">Điện thoại:</span> {intake.phone ?? '—'}</div>
            <div><span className="text-subink">Mail:</span> {intake.email ?? '—'}</div>
          </div>
        ) : null}

        {/* Thông tin mẫu (không nhạy cảm) */}
        <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2 gap-y-2 text-sm">
          <div className="sm:col-span-2"><span className="text-subink">Mô tả mẫu:</span> {intake?.description ?? '—'}</div>
          <div><span className="text-subink">Ngày hẹn trả KQ:</span> {intake?.due_date ?? '—'}</div>
          <div>
            <span className="text-subink">Trạng thái:</span>{' '}
            <Badge tone={DISPATCH_TONE[dispatch.status]}>{DISPATCH_STATUS_LABELS[dispatch.status]}</Badge>
          </div>
        </div>

        {/* Chi tiết chỉ tiêu */}
        <div>
          <div className="mb-2 text-sm font-semibold text-ink">Chỉ tiêu thực hiện</div>
          <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2 gap-y-2 rounded-xl border border-hairline p-4 text-sm">
            <div className="sm:col-span-2"><span className="text-subink">Chỉ tiêu:</span> <span className="font-medium text-ink">{dispatch.chi_tieu}</span></div>
            <div><span className="text-subink">Đơn vị:</span> {dispatch.don_vi ?? '—'}</div>
            <div><span className="text-subink">Phương pháp:</span> {dispatch.phuong_phap ?? '—'}</div>
            <div><span className="text-subink">Kết quả:</span> <span className="font-medium text-ink">{dispatch.ket_qua ?? '—'}</span></div>
            <div><span className="text-subink">Cán bộ phân tích:</span> {dispatch.can_bo ?? '—'}</div>
            {dispatch.note && <div className="sm:col-span-2"><span className="text-subink">Ghi chú:</span> {dispatch.note}</div>}
          </div>
        </div>

        {/* Mốc thời gian */}
        <div>
          <div className="mb-2 text-sm font-semibold text-ink">Tiến trình</div>
          <div className="flex flex-col gap-1.5 text-sm">
            <div><span className="text-subink">Chuyển đến phòng:</span> {dispatch.dispatched_at ? formatDateTime(dispatch.dispatched_at) : '—'}{dispatch.dispatched_by_name ? ` · ${dispatch.dispatched_by_name}` : ''}</div>
            <div><span className="text-subink">Phòng tiếp nhận:</span> {dispatch.received_at ? formatDateTime(dispatch.received_at) : '—'}</div>
            <div><span className="text-subink">Hoàn thành:</span> {dispatch.completed_at ? formatDateTime(dispatch.completed_at) : '—'}</div>
          </div>
        </div>

        {/* Tệp đính kèm của chỉ tiêu */}
        <div>
          <div className="mb-1 text-sm font-semibold text-ink">Tệp đính kèm</div>
          {dispatch.files.length === 0 ? (
            <p className="text-sm text-subink">Chưa có tệp.</p>
          ) : (
            dispatch.files.map((f) => (
              <button
                key={f.id}
                className="flex items-center gap-1 text-sm text-blueberry hover:underline"
                onClick={() => flowApi.openFile(f.id).catch((e) => toast.error(describeError(e).title))}
              >
                <Download size={13} /> {f.file_name}
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}

/**
 * Chi tiết + SỬA 1 dòng chỉ tiêu của phiếu chuyển (BM 7.1.02).
 * Mở khi bấm vào dòng trong bảng "Chỉ tiêu đã chuyển".
 */
function DispatchEditModal({
  dispatch, canEdit, onClose, onSaved,
}: {
  dispatch: SampleDispatch; canEdit: boolean; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({
    sample_name: dispatch.sample_name ?? '',
    quantity: String(dispatch.quantity ?? 1),
    don_vi: dispatch.don_vi ?? '',
    phuong_phap: dispatch.phuong_phap ?? '',
    ket_qua: dispatch.ket_qua ?? '',
    can_bo: dispatch.can_bo ?? '',
    note: dispatch.note ?? '',
    status: dispatch.status,
  });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  async function save() {
    setSaving(true);
    try {
      await flowApi.updateDispatch(dispatch.id, {
        sample_name: f.sample_name.trim() || null,
        quantity: Number(f.quantity) || 1,
        don_vi: f.don_vi.trim() || null,
        phuong_phap: f.phuong_phap.trim() || null,
        ket_qua: f.ket_qua.trim() || null,
        can_bo: f.can_bo.trim() || null,
        note: f.note.trim() || null,
        status: f.status as DispatchStatus,
      });
      toast.success('Đã cập nhật chỉ tiêu');
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
      title={dispatch.chi_tieu}
      description={`Phiếu ${dispatch.intake_code ?? ''} · ${dispatch.target_department_name ?? ''}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Đóng</Button>
          {canEdit && <Button onClick={save} loading={saving}>Lưu thay đổi</Button>}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Thông tin không sửa được */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 rounded-lg bg-plate p-3 text-sm">
          <div><span className="text-subink">Chỉ tiêu:</span> <span className="font-medium text-ink">{dispatch.chi_tieu}</span></div>
          <div><span className="text-subink">Phòng lab:</span> {dispatch.target_department_name ?? '—'}</div>
          <div>
            <span className="text-subink">Từ danh mục:</span>{' '}
            {dispatch.test_parameter_id ? <Badge tone="success">Có</Badge> : <Badge tone="muted">Nhập tự do</Badge>}
          </div>
          <div>
            <span className="text-subink">Đơn giá:</span>{' '}
            {dispatch.unit_price ? formatMoney(dispatch.unit_price) : '—'}
          </div>
          <div><span className="text-subink">Chuyển lúc:</span> {dispatch.dispatched_at ? formatDateTime(dispatch.dispatched_at) : '—'}</div>
          <div><span className="text-subink">Hoàn thành:</span> {dispatch.completed_at ? formatDateTime(dispatch.completed_at) : '—'}</div>
        </div>

        {/* Các cột BM 7.1.02 sửa được */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Loại / Tên mẫu" className="md:col-span-2">
            <Input value={f.sample_name} onChange={set('sample_name')} disabled={!canEdit} />
          </Field>
          <Field label="Số lượng">
            <Input type="number" min={1} value={f.quantity} onChange={set('quantity')} disabled={!canEdit} />
          </Field>
          <Field label="Đơn vị">
            <Input value={f.don_vi} onChange={set('don_vi')} disabled={!canEdit} placeholder="mg/L, CFU/g…" />
          </Field>
          <Field label="Phương pháp thử nghiệm" className="md:col-span-2">
            <Input value={f.phuong_phap} onChange={set('phuong_phap')} disabled={!canEdit} />
          </Field>
          <Field label="Kết quả">
            <Input value={f.ket_qua} onChange={set('ket_qua')} disabled={!canEdit} />
          </Field>
          <Field label="Cán bộ phân tích">
            <Input value={f.can_bo} onChange={set('can_bo')} disabled={!canEdit} />
          </Field>
          <Field label="Trạng thái">
            <Select value={f.status} onChange={set('status')} disabled={!canEdit}>
              {(Object.keys(DISPATCH_STATUS_LABELS) as DispatchStatus[]).map((s) => (
                <option key={s} value={s}>{DISPATCH_STATUS_LABELS[s]}</option>
              ))}
            </Select>
          </Field>
          <Field label="Ghi chú" className="md:col-span-2">
            <Textarea rows={2} value={f.note} onChange={set('note')} disabled={!canEdit} />
          </Field>
        </div>

        {/* Tệp đính kèm của chỉ tiêu */}
        {dispatch.files.length > 0 && (
          <div>
            <div className="mb-1 text-sm font-semibold text-ink">Tệp đính kèm</div>
            {dispatch.files.map((file) => (
              <button
                key={file.id}
                className="flex items-center gap-1 text-sm text-blueberry hover:underline"
                onClick={() => flowApi.openFile(file.id).catch((e) => toast.error(describeError(e).title))}
              >
                <Download size={13} /> {file.file_name}
              </button>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}
