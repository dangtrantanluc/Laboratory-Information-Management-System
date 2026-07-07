import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Plus, CheckCircle2, Circle, Lock } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { DescList, DescItem } from '@/components/ui/DescList';
import { RiskKindBadge, RiskStatusBadge, RiskBandBadge } from '@/components/ui/StatusBadge';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate, formatDateTime } from '@/lib/format';
import { canManageRisk } from '@/lib/rbac';
import { RISK_STATUS_LABELS, type RiskDetail as RiskDetailT, type RiskStatus, type RiskTreatmentItem } from '@/types';
import * as riskApi from '@/api/risks';
import * as usersApi from '@/api/users';

export function RiskDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: risk, loading, reload } = useAsync(() => riskApi.getRisk(id), [id]);
  const [treatOpen, setTreatOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  if (loading) return <LoadingState label="Đang tải rủi ro…" />;
  if (!risk)
    return <Card><EmptyState icon={<AlertTriangle size={22} />} title="Không tìm thấy rủi ro" /></Card>;

  const canManage = canManageRisk(user);
  const isOpen = risk.status !== 'closed';

  return (
    <div className="flex flex-col gap-5">
      <div>
        <button onClick={() => navigate('/risks')} className="mb-3 inline-flex items-center gap-1.5 text-sm text-stem hover:text-ink">
          <ArrowLeft size={16} /> Sổ rủi ro
        </button>
        <PageHeader
          title={risk.title}
          description={`${risk.risk_code} · ${risk.process_ref ?? 'Chưa gắn tiến trình'}`}
          icon={<AlertTriangle size={20} />}
          actions={
            <div className="flex items-center gap-2">
              <RiskKindBadge kind={risk.kind} />
              <RiskBandBadge band={risk.band} level={risk.level} />
              <RiskStatusBadge status={risk.status} />
            </div>
          }
        />
      </div>

      <Card>
        <CardHeader title="Thông tin rủi ro / cơ hội" />
        <CardBody>
          <DescList>
            <DescItem label="Bối cảnh" value={<span className="whitespace-pre-wrap">{risk.context}</span>} />
            <DescItem label="Khả năng × Tác động" value={`${risk.likelihood} × ${risk.impact} = ${risk.level}`} />
            <DescItem label="Phòng ban" value={risk.department_name} />
            <DescItem label="Phụ trách" value={risk.owner_name} />
            <DescItem label="Đánh giá lại" value={formatDate(risk.next_review_date ?? undefined)} />
            {risk.status === 'closed' && <DescItem label="Đóng bởi" value={`${risk.closed_by_name ?? '—'} · ${formatDateTime(risk.closed_at ?? '')}`} />}
          </DescList>
          {isOpen && canManage && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
              <Button variant="secondary" onClick={() => setEditOpen(true)}>Sửa đánh giá</Button>
              <Button variant="ghost" onClick={() => setTreatOpen(true)}><Plus size={16} /> Thêm biện pháp</Button>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Biện pháp xử lý (§8.5.2)"
          action={risk.status === 'closed' ? (
            <span className="inline-flex items-center gap-1 text-xs text-subink"><Lock size={12} /> Đã đóng</span>
          ) : undefined}
        />
        <CardBody>
          {risk.treatments.length === 0 ? (
            <p className="py-2 text-sm text-subink">Chưa có biện pháp xử lý.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {risk.treatments.map((t) => (
                <TreatmentRow key={t.id} treatment={t} riskId={risk.id} canToggle={isOpen && canManage} onDone={reload} />
              ))}
            </ul>
          )}
          {isOpen && canManage && (
            <div className="mt-4 flex justify-end border-t border-hairline pt-4">
              <Button onClick={() => setCloseOpen(true)}><CheckCircle2 size={16} /> Đóng rủi ro (đã kiểm soát)</Button>
            </div>
          )}
        </CardBody>
      </Card>

      {treatOpen && <TreatmentModal risk={risk} onClose={() => setTreatOpen(false)} onDone={() => { setTreatOpen(false); reload(); }} />}
      {closeOpen && <CloseModal risk={risk} onClose={() => setCloseOpen(false)} onDone={() => { setCloseOpen(false); reload(); }} />}
      {editOpen && <EditModal risk={risk} onClose={() => setEditOpen(false)} onDone={() => { setEditOpen(false); reload(); }} />}
    </div>
  );
}

function TreatmentRow({ treatment: t, riskId, canToggle, onDone }: { treatment: RiskTreatmentItem; riskId: string; canToggle: boolean; onDone: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const done = t.status === 'done';
  async function toggle() {
    if (!canToggle || busy) return;
    setBusy(true);
    try {
      await riskApi.updateTreatment(riskId, t.id, done ? 'todo' : 'done');
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className="flex items-start gap-2.5 rounded-lg border border-hairline px-3 py-2.5">
      <button onClick={toggle} disabled={!canToggle || busy} className={done ? 'text-success' : 'text-stem hover:text-ink'}>
        {done ? <CheckCircle2 size={18} /> : <Circle size={18} />}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`text-sm ${done ? 'text-subink line-through' : 'text-ink'}`}>{t.treatment}</p>
        <p className="mt-0.5 text-xs text-subink">
          {t.owner_name ? `Phụ trách: ${t.owner_name}` : 'Chưa giao'}
          {t.due_date ? ` · Hạn: ${formatDate(t.due_date)}` : ''}
        </p>
      </div>
    </li>
  );
}

function TreatmentModal({ risk, onClose, onDone }: { risk: RiskDetailT; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [treatment, setTreatment] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  async function submit() {
    if (!treatment.trim()) return toast.error('Nhập biện pháp');
    setSubmitting(true);
    try {
      await riskApi.addTreatment(risk.id, { treatment: treatment.trim(), owner_id: ownerId || null, due_date: dueDate || null });
      toast.success('Đã thêm biện pháp');
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Thêm biện pháp xử lý"
      footer={<><Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button><Button onClick={submit} loading={submitting}>Thêm</Button></>}>
      <div className="flex flex-col gap-4">
        <Field label="Biện pháp" required><Textarea value={treatment} onChange={(e) => setTreatment(e.target.value)} rows={2} /></Field>
        <Field label="Người thực hiện">
          <Select value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
            <option value="">— Chưa giao —</option>
            {(users?.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </Select>
        </Field>
        <Field label="Hạn hoàn thành"><Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

function CloseModal({ risk, onClose, onDone }: { risk: RiskDetailT; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  async function submit() {
    setSubmitting(true);
    try {
      await riskApi.closeRisk(risk.id, note.trim() || undefined);
      toast.success('Đã đóng rủi ro');
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Đóng rủi ro" description="Xác nhận rủi ro đã được kiểm soát ở mức chấp nhận được."
      footer={<><Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button><Button onClick={submit} loading={submitting}>Đóng rủi ro</Button></>}>
      <Field label="Ghi chú"><Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} /></Field>
    </Modal>
  );
}

function EditModal({ risk, onClose, onDone }: { risk: RiskDetailT; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [likelihood, setLikelihood] = useState(risk.likelihood);
  const [impact, setImpact] = useState(risk.impact);
  const [status, setStatus] = useState<RiskStatus>(risk.status);
  const [reviewDate, setReviewDate] = useState(risk.next_review_date ?? '');
  const [submitting, setSubmitting] = useState(false);
  async function submit() {
    setSubmitting(true);
    try {
      await riskApi.updateRisk(risk.id, { likelihood, impact, status, next_review_date: reviewDate || null });
      toast.success('Đã cập nhật');
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Cập nhật đánh giá rủi ro"
      footer={<><Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button><Button onClick={submit} loading={submitting}>Lưu</Button></>}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Khả năng (1–5)">
          <Select value={String(likelihood)} onChange={(e) => setLikelihood(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field label="Tác động (1–5)">
          <Select value={String(impact)} onChange={(e) => setImpact(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field label="Trạng thái">
          <Select value={status} onChange={(e) => setStatus(e.target.value as RiskStatus)}>
            {(Object.keys(RISK_STATUS_LABELS) as RiskStatus[]).filter((s) => s !== 'closed').map((s) => (
              <option key={s} value={s}>{RISK_STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </Field>
        <Field label="Đánh giá lại"><Input type="date" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
