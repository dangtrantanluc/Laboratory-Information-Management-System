import { useState } from 'react';
import { Check, CircleDollarSign, AlertTriangle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { formatMoney } from '@/lib/format';
import { cn } from '@/lib/cn';
import {
  INTAKE_FLOW,
  INTAKE_STATUS_LABELS,
  PAYMENT_STATUS_LABELS,
  type IntakeStatus,
  type PaymentStatus,
  type SampleIntake,
} from '@/types';
import * as flowApi from '@/api/sampleFlow';

export const INTAKE_TONE: Record<IntakeStatus, BadgeTone> = {
  received: 'neutral',
  quoted: 'info',
  quote_accepted: 'pending',
  paid: 'success',
  dispatched: 'warning',
  completed: 'success',
  cancelled: 'overdue',
};

const PAYMENT_TONE: Record<PaymentStatus, BadgeTone> = {
  unpaid: 'overdue',
  partial: 'warning',
  paid: 'success',
  waived: 'muted',
};

export function IntakeStatusBadge({ status }: { status: IntakeStatus }) {
  return <Badge tone={INTAKE_TONE[status] ?? 'neutral'}>{INTAKE_STATUS_LABELS[status] ?? status}</Badge>;
}

export function PaymentBadge({ status }: { status?: PaymentStatus }) {
  if (!status) return <span className="text-subink">—</span>;
  return <Badge tone={PAYMENT_TONE[status]} dot>{PAYMENT_STATUS_LABELS[status]}</Badge>;
}

/**
 * Khối theo dõi tiến trình phiếu (m28): thanh 6 bước + nút chuyển bước hợp lệ
 * + ghi nhận thanh toán + CẢNH BÁO khi chuyển lab mà khách chưa thanh toán.
 */
export function IntakeWorkflow({
  intake,
  canManage,
  onChanged,
}: {
  intake: SampleIntake;
  canManage: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [payOpen, setPayOpen] = useState(false);

  const status = intake.status;
  const flowIdx = INTAKE_FLOW.indexOf(status);
  const cancelled = status === 'cancelled';
  const unpaid = intake.payment_status === 'unpaid' || intake.payment_status === 'partial';
  // Cảnh báo (không chặn): chuyển lab khi khách chưa thanh toán đủ
  const showPayWarning = unpaid && ['received', 'quoted', 'quote_accepted'].includes(status);

  async function go(next: IntakeStatus) {
    setBusy(next);
    try {
      await flowApi.changeIntakeStatus(intake.id, next);
      toast.success(`Đã chuyển sang "${INTAKE_STATUS_LABELS[next]}"`);
      onChanged();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-xl border border-hairline bg-plate p-4">
      {/* Thanh tiến trình 6 bước */}
      <div className="flex flex-wrap items-center gap-y-2">
        {INTAKE_FLOW.map((s, i) => {
          const done = !cancelled && flowIdx >= i;
          const current = !cancelled && flowIdx === i;
          return (
            <div key={s} className="flex items-center">
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold',
                    done ? 'bg-blueberry text-white' : 'bg-hairline text-stem',
                    current && 'ring-2 ring-blueberry/30',
                  )}
                >
                  {done ? <Check size={12} /> : i + 1}
                </span>
                <span className={cn('text-xs', current ? 'font-semibold text-ink' : 'text-subink')}>
                  {INTAKE_STATUS_LABELS[s]}
                </span>
              </div>
              {i < INTAKE_FLOW.length - 1 && (
                <span className={cn('mx-2 h-px w-5', done ? 'bg-blueberry' : 'bg-hairline')} />
              )}
            </div>
          );
        })}
        {cancelled && (
          <Badge tone="overdue" className="ml-2">
            <XCircle size={12} /> Đã hủy
          </Badge>
        )}
      </div>

      {/* Thanh toán */}
      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-hairline pt-3 text-sm">
        <span className="flex items-center gap-1.5 text-subink">
          <CircleDollarSign size={14} /> Thanh toán:
        </span>
        <PaymentBadge status={intake.payment_status} />
        {intake.paid_amount && <span className="font-medium text-ink">{formatMoney(intake.paid_amount)}</span>}
        {intake.payment_ref && <span className="text-xs text-subink">Mã CK: {intake.payment_ref}</span>}
        {canManage && (
          <Button size="sm" variant="secondary" onClick={() => setPayOpen(true)}>
            Ghi nhận thanh toán
          </Button>
        )}
      </div>

      {/* Cảnh báo chưa thanh toán (không chặn) */}
      {showPayWarning && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-xs text-ink">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warning" />
          <span>
            Khách hàng <strong>chưa thanh toán đủ</strong>. Nên báo giá và nhận thanh toán trước khi chuyển
            mẫu cho phòng lab (vẫn có thể chuyển nếu cần).
          </span>
        </div>
      )}

      {/* Nút chuyển bước */}
      {canManage && (intake.next_statuses?.length ?? 0) > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
          <span className="text-xs text-subink">Chuyển bước:</span>
          {intake.next_statuses!.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={s === 'cancelled' ? 'secondary' : 'primary'}
              loading={busy === s}
              onClick={() => go(s)}
            >
              {INTAKE_STATUS_LABELS[s]}
            </Button>
          ))}
        </div>
      )}

      {payOpen && (
        <PaymentModal
          intake={intake}
          onClose={() => setPayOpen(false)}
          onSaved={() => { setPayOpen(false); onChanged(); }}
        />
      )}
    </div>
  );
}

function PaymentModal({
  intake, onClose, onSaved,
}: {
  intake: SampleIntake; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({
    payment_status: (intake.payment_status ?? 'unpaid') as PaymentStatus,
    paid_amount: intake.paid_amount ?? '',
    payment_date: intake.payment_date ?? '',
    payment_ref: intake.payment_ref ?? '',
    payment_note: intake.payment_note ?? '',
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await flowApi.updateIntakePayment(intake.id, {
        payment_status: f.payment_status,
        paid_amount: f.paid_amount.toString().trim() || null,
        payment_date: f.payment_date || null,
        payment_ref: f.payment_ref.trim() || null,
        payment_note: f.payment_note.trim() || null,
      });
      toast.success('Đã ghi nhận thanh toán');
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
      title="Ghi nhận thanh toán"
      description={`Phiếu ${intake.code}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Hủy</Button>
          <Button onClick={save} loading={saving}>Lưu</Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Trạng thái thanh toán" required>
          <Select
            value={f.payment_status}
            onChange={(e) => setF((p) => ({ ...p, payment_status: e.target.value as PaymentStatus }))}
          >
            {(Object.keys(PAYMENT_STATUS_LABELS) as PaymentStatus[]).map((s) => (
              <option key={s} value={s}>{PAYMENT_STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </Field>
        <Field label="Số tiền đã nhận (VNĐ)">
          <Input
            value={f.paid_amount}
            onChange={(e) => setF((p) => ({ ...p, paid_amount: e.target.value }))}
            placeholder="224208000"
          />
        </Field>
        <Field label="Ngày thanh toán">
          <Input
            type="date"
            value={f.payment_date ?? ''}
            onChange={(e) => setF((p) => ({ ...p, payment_date: e.target.value }))}
          />
        </Field>
        <Field label="Mã giao dịch / số UNC">
          <Input
            value={f.payment_ref}
            onChange={(e) => setF((p) => ({ ...p, payment_ref: e.target.value }))}
            placeholder="VD: UNC-98765"
          />
        </Field>
        <Field label="Ghi chú" className="md:col-span-2">
          <Textarea
            rows={2}
            value={f.payment_note}
            onChange={(e) => setF((p) => ({ ...p, payment_note: e.target.value }))}
          />
        </Field>
      </div>
    </Modal>
  );
}
