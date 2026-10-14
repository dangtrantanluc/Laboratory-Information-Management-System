/** Hộp thoại chuyển trạng thái báo cáo quý: lab nộp; Văn phòng trả lại / mở khoá (có lý do). */
import { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Field, Textarea } from '@/components/ui/Field';

export function SubmitModal({
  itemCount,
  totalQuantity,
  period,
  loading,
  onClose,
  onConfirm,
}: {
  itemCount: number;
  totalQuantity: number;
  period: string;
  loading: boolean;
  onClose: () => void;
  onConfirm: (body: { lab_note: string | null; confirm_empty: boolean }) => void;
}) {
  const [note, setNote] = useState('');
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const empty = itemCount === 0;
  return (
    <Modal
      open
      onClose={onClose}
      size="md"
      title={`Nộp báo cáo mẫu ${period}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Hủy
          </Button>
          <Button
            onClick={() => onConfirm({ lab_note: note.trim() || null, confirm_empty: confirmEmpty })}
            loading={loading}
            disabled={empty && !confirmEmpty}
          >
            Nộp cho Văn phòng
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 text-sm">
        {empty ? (
          <label className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3">
            <input type="checkbox" className="mt-0.5" checked={confirmEmpty} onChange={(e) => setConfirmEmpty(e.target.checked)} />
            <span>
              Báo cáo chưa có mẫu nào. Tôi xác nhận <b>phòng không phát sinh mẫu</b> trong {period}.
            </span>
          </label>
        ) : (
          <p className="text-ink">
            Nộp <b>{itemCount}</b> dòng mẫu (tổng <b>{totalQuantity}</b> mẫu). Sau khi nộp, phòng không sửa được nữa
            cho tới khi Văn phòng trả lại.
          </p>
        )}
        <Field label="Ghi chú gửi Văn phòng">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
        </Field>
      </div>
    </Modal>
  );
}

export function ReasonModal({
  title,
  description,
  confirmText,
  loading,
  onClose,
  onConfirm,
}: {
  title: string;
  description: string;
  confirmText: string;
  loading: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const ok = reason.trim().length >= 3;
  return (
    <Modal
      open
      onClose={onClose}
      size="md"
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Hủy
          </Button>
          <Button variant="danger" onClick={() => onConfirm(reason.trim())} loading={loading} disabled={!ok}>
            {confirmText}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-subink">{description}</p>
        <Field label="Lý do" required hint="Phòng lab sẽ thấy lý do này">
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="vd: Mẫu 26N267 thiếu chỉ tiêu phân tích"
            autoFocus
          />
        </Field>
      </div>
    </Modal>
  );
}
