import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ShieldAlert,
  Plus,
  CheckCircle2,
  Circle,
  Lock,
  Ban,
  ClipboardCheck,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Badge } from '@/components/ui/Badge';
import { NcSeverityBadge, NcStatusBadge } from '@/components/ui/StatusBadge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canManageCapa } from '@/lib/rbac';
import {
  CAPA_TYPE_LABELS,
  CAPA_EFFECTIVENESS_LABELS,
  type CapaActionItem,
  type CapaEffectiveness,
  type CapaType,
  type NcDetail,
} from '@/types';
import * as ncApi from '@/api/nonconformities';
import * as usersApi from '@/api/users';

export function NonconformityDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: nc, loading, reload } = useAsync(() => ncApi.getNonconformity(id), [id]);
  const [openCapaOpen, setOpenCapaOpen] = useState(false);
  const [addActionOpen, setAddActionOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  if (loading) return <LoadingState label="Đang tải phiếu…" />;
  if (!nc)
    return (
      <Card>
        <EmptyState icon={<ShieldAlert size={22} />} title="Không tìm thấy phiếu" />
      </Card>
    );

  const canManage = canManageCapa(user);
  const capa = nc.capa;
  const capaOpen = capa?.status === 'in_progress';

  return (
    <div className="flex flex-col gap-5">
      <div>
        <button
          onClick={() => navigate('/nonconformities')}
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-stem hover:text-ink"
        >
          <ArrowLeft size={16} /> Danh sách NC
        </button>
        <PageHeader
          title={nc.title}
          description={`${nc.nc_code} · Nguồn: ${nc.source_label}`}
          icon={<ShieldAlert size={20} />}
          actions={
            <div className="flex items-center gap-2">
              <NcSeverityBadge severity={nc.severity} />
              <NcStatusBadge status={nc.status} />
            </div>
          }
        />
      </div>

      {nc.warning && (
        <div className="rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-[#b45309]">
          ⚠ {nc.warning}
        </div>
      )}

      {/* NC info */}
      <Card>
        <CardHeader title="Thông tin không phù hợp" />
        <CardBody>
          <DescList>
            <DescItem label="Mô tả" value={<span className="whitespace-pre-wrap">{nc.description}</span>} />
            <DescItem label="Đánh giá tác động (§7.10.1)" value={nc.impact_assessment} />
            <DescItem label="Phòng ban" value={nc.department_name} />
            <DescItem label="Người mở" value={nc.raised_by_name} />
            <DescItem label="Thời điểm mở" value={formatDateTime(nc.raised_at)} />
          </DescList>
          {nc.status === 'open' && canManage && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
              <Button onClick={() => setOpenCapaOpen(true)}>
                <ClipboardCheck size={16} /> Mở CAPA
              </Button>
              <Button variant="ghost" onClick={() => setCancelOpen(true)}>
                <Ban size={16} /> Hủy phiếu (không hợp lệ)
              </Button>
            </div>
          )}
        </CardBody>
      </Card>

      {/* CAPA */}
      {capa ? (
        <Card>
          <CardHeader
            title="Hành động khắc phục (CAPA §8.7)"
            action={
              capa.status === 'closed' ? (
                <Badge tone="success" dot>
                  <Lock size={12} /> Đã đóng — bất biến
                </Badge>
              ) : (
                <Badge tone="pending" dot>
                  Đang thực hiện
                </Badge>
              )
            }
          />
          <CardBody>
            <DescList>
              <DescItem label="Loại" value={CAPA_TYPE_LABELS[capa.capa_type]} />
              <DescItem label="Người phụ trách" value={capa.owner_name} />
              <DescItem label="Hạn xử lý" value={formatDate(capa.due_date ?? undefined)} />
              <DescItem label="Nguyên nhân gốc" value={<span className="whitespace-pre-wrap">{capa.root_cause}</span>} />
              {capa.status === 'closed' && (
                <>
                  <DescItem
                    label="Hiệu lực"
                    value={
                      capa.effectiveness_result ? (
                        <Badge tone={capa.effectiveness_result === 'effective' ? 'success' : 'overdue'}>
                          {CAPA_EFFECTIVENESS_LABELS[capa.effectiveness_result]}
                        </Badge>
                      ) : null
                    }
                  />
                  <DescItem label="Ghi chú hiệu lực" value={capa.effectiveness_note} />
                  <DescItem label="Người đóng" value={capa.closed_by_name} />
                  <DescItem label="Thời điểm đóng" value={formatDateTime(capa.closed_at ?? '')} />
                </>
              )}
            </DescList>

            {/* Actions */}
            <div className="mt-4 border-t border-hairline pt-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-ink">
                  Hành động khắc phục ({capa.actions.length})
                </p>
                {capaOpen && canManage && (
                  <Button size="sm" variant="secondary" onClick={() => setAddActionOpen(true)}>
                    <Plus size={14} /> Thêm hành động
                  </Button>
                )}
              </div>
              {capa.actions.length === 0 ? (
                <p className="py-3 text-sm text-subink">Chưa có hành động nào.</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {capa.actions.map((a) => (
                    <ActionRow
                      key={a.id}
                      action={a}
                      canToggle={capaOpen && canManage}
                      onToggle={async (next) => {
                        try {
                          await ncApi.updateCapaAction(nc.id, a.id, next);
                          reload();
                        } catch (err) {
                          // toast handled by caller-less; surface minimal
                          throw err;
                        }
                      }}
                    />
                  ))}
                </ul>
              )}
            </div>

            {capaOpen && canManage && (
              <div className="mt-4 flex justify-end border-t border-hairline pt-4">
                <Button onClick={() => setCloseOpen(true)}>
                  <CheckCircle2 size={16} /> Xác minh hiệu lực & đóng CAPA
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      ) : (
        nc.status !== 'cancelled' && (
          <Card>
            <CardBody>
              <EmptyState
                icon={<ClipboardCheck size={22} />}
                title="Chưa mở CAPA"
                description={
                  canManage
                    ? 'Phân tích nguyên nhân gốc và lập hành động khắc phục.'
                    : 'Chờ Phụ trách chất lượng (QM) mở CAPA.'
                }
                action={
                  nc.status === 'open' && canManage ? (
                    <Button onClick={() => setOpenCapaOpen(true)}>
                      <ClipboardCheck size={16} /> Mở CAPA
                    </Button>
                  ) : undefined
                }
              />
            </CardBody>
          </Card>
        )
      )}

      {openCapaOpen && (
        <OpenCapaModal nc={nc} onClose={() => setOpenCapaOpen(false)} onDone={() => { setOpenCapaOpen(false); reload(); }} />
      )}
      {addActionOpen && (
        <AddActionModal nc={nc} onClose={() => setAddActionOpen(false)} onDone={() => { setAddActionOpen(false); reload(); }} />
      )}
      {closeOpen && (
        <CloseCapaModal nc={nc} onClose={() => setCloseOpen(false)} onDone={() => { setCloseOpen(false); reload(); }} />
      )}
      {cancelOpen && (
        <CancelModal nc={nc} onClose={() => setCancelOpen(false)} onDone={() => { setCancelOpen(false); reload(); }} />
      )}
    </div>
  );
}

function ActionRow({
  action,
  canToggle,
  onToggle,
}: {
  action: CapaActionItem;
  canToggle: boolean;
  onToggle: (next: 'todo' | 'done') => Promise<void>;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const done = action.status === 'done';

  async function toggle() {
    if (!canToggle || busy) return;
    setBusy(true);
    try {
      await onToggle(done ? 'todo' : 'done');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex items-start gap-2.5 rounded-lg border border-hairline px-3 py-2.5">
      <button
        onClick={toggle}
        disabled={!canToggle || busy}
        className={done ? 'text-success' : 'text-stem hover:text-ink'}
        title={canToggle ? 'Đánh dấu hoàn thành' : undefined}
      >
        {done ? <CheckCircle2 size={18} /> : <Circle size={18} />}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`text-sm ${done ? 'text-subink line-through' : 'text-ink'}`}>{action.action}</p>
        <p className="mt-0.5 text-xs text-subink">
          {action.assignee_name ? `Phụ trách: ${action.assignee_name}` : 'Chưa giao'}
          {action.due_date ? ` · Hạn: ${formatDate(action.due_date)}` : ''}
          {done && action.done_at ? ` · Xong: ${formatDate(action.done_at)}` : ''}
        </p>
      </div>
    </li>
  );
}

function OpenCapaModal({ nc, onClose, onDone }: { nc: NcDetail; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [rootCause, setRootCause] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [capaType, setCapaType] = useState<CapaType>('corrective');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);

  async function submit() {
    if (!rootCause.trim()) return toast.error('Nhập nguyên nhân gốc');
    if (!ownerId) return toast.error('Chọn người phụ trách CAPA');
    setSubmitting(true);
    try {
      await ncApi.openCapa(nc.id, {
        root_cause: rootCause.trim(),
        owner_id: ownerId,
        capa_type: capaType,
        due_date: dueDate || null,
      });
      toast.success('Đã mở CAPA');
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
      size="lg"
      title="Mở CAPA — Hành động khắc phục"
      description="Phân tích nguyên nhân gốc (5-why / biểu đồ xương cá) và giao người phụ trách."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Mở CAPA
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Nguyên nhân gốc (§8.7.2)" required className="sm:col-span-2">
          <Textarea value={rootCause} onChange={(e) => setRootCause(e.target.value)} rows={3} placeholder="Vì sao xảy ra không phù hợp…" />
        </Field>
        <Field label="Loại CAPA">
          <Select value={capaType} onChange={(e) => setCapaType(e.target.value as CapaType)}>
            {(Object.keys(CAPA_TYPE_LABELS) as CapaType[]).map((t) => (
              <option key={t} value={t}>
                {CAPA_TYPE_LABELS[t]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Hạn xử lý">
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
        <Field label="Người phụ trách CAPA" required className="sm:col-span-2">
          <Select value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
            <option value="">— Chọn người phụ trách —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function AddActionModal({ nc, onClose, onDone }: { nc: NcDetail; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [action, setAction] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);

  async function submit() {
    if (!action.trim()) return toast.error('Nhập nội dung hành động');
    setSubmitting(true);
    try {
      await ncApi.addCapaAction(nc.id, {
        action: action.trim(),
        assignee_id: assigneeId || null,
        due_date: dueDate || null,
      });
      toast.success('Đã thêm hành động');
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
      title="Thêm hành động khắc phục"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Thêm
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Nội dung hành động" required>
          <Textarea value={action} onChange={(e) => setAction(e.target.value)} rows={2} />
        </Field>
        <Field label="Người thực hiện">
          <Select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
            <option value="">— Chưa giao —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Hạn hoàn thành">
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function CloseCapaModal({ nc, onClose, onDone }: { nc: NcDetail; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [result, setResult] = useState<CapaEffectiveness>('effective');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const pending = (nc.capa?.actions ?? []).filter((a) => a.status !== 'done').length;

  async function submit() {
    setSubmitting(true);
    try {
      const res = await ncApi.closeCapa(nc.id, { effectiveness_result: result, effectiveness_note: note.trim() || null });
      toast.success(`Đã đóng CAPA của ${res.nc_code}`);
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
      title="Xác minh hiệu lực & đóng CAPA"
      description="Sau khi đóng, CAPA trở thành hồ sơ BẤT BIẾN (§8.7) — không thể sửa."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting} disabled={pending > 0}>
            Đóng CAPA
          </Button>
        </>
      }
    >
      {pending > 0 ? (
        <div className="rounded-lg border border-overdue/30 bg-overdue/5 px-3 py-2.5 text-sm text-overdue">
          Còn {pending} hành động chưa hoàn thành — hãy đánh dấu hoàn thành trước khi đóng.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <Field label="Kết quả xác minh hiệu lực (§8.7.3)" required>
            <Select value={result} onChange={(e) => setResult(e.target.value as CapaEffectiveness)}>
              {(Object.keys(CAPA_EFFECTIVENESS_LABELS) as CapaEffectiveness[]).map((r) => (
                <option key={r} value={r}>
                  {CAPA_EFFECTIVENESS_LABELS[r]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Ghi chú">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </Field>
        </div>
      )}
    </Modal>
  );
}

function CancelModal({ nc, onClose, onDone }: { nc: NcDetail; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!reason.trim()) return toast.error('Nhập lý do hủy');
    setSubmitting(true);
    try {
      await ncApi.cancelNonconformity(nc.id, reason.trim());
      toast.success('Đã hủy phiếu');
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
      title="Hủy phiếu không phù hợp"
      description="Dùng khi phiếu không hợp lệ. Không thể hủy khi đã mở CAPA."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Đóng
          </Button>
          <Button variant="danger" onClick={submit} loading={submitting}>
            Xác nhận hủy
          </Button>
        </>
      }
    >
      <Field label="Lý do hủy" required>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
      </Field>
    </Modal>
  );
}
