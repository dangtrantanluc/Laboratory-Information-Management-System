/**
 * Modal "Nhập kết quả" cho một lượt chuyển mẫu (BM 7.1/02).
 *
 * Tách khỏi SampleFlow.tsx vì file đó đã chạm trần kích thước (xem
 * scripts/check-file-size.mjs — trần chỉ được HẠ, không được nới), cùng chỗ với
 * IntakeCreateModal đã tách trước đó.
 *
 * Các ô ở đây đúng bằng các cột lab điền trên BM 7.1/02: Đơn vị · Phương pháp thử ·
 * Kết quả. Từ m37, người mở modal này là NGƯỜI THỰC HIỆN phép thử (KTV/trưởng phòng
 * lab), và ô "Cán bộ phân tích" đã bỏ: danh tính lấy từ tài khoản đăng nhập chứ
 * không gõ tay, nếu không thì truy xuất theo ISO/IEC 17025 §7.8.2 chỉ là hình thức.
 */
import { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Textarea } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import type { SampleDispatch } from '@/types';
import * as flowApi from '@/api/sampleFlow';

export function DispatchResultModal({
  dispatch, onClose, onDone,
}: {
  dispatch: SampleDispatch; onClose: () => void; onDone: () => void;
}) {
  const toast = useToast();
  const [v, setV] = useState({
    don_vi: dispatch.don_vi ?? '', phuong_phap: dispatch.phuong_phap ?? '',
    ket_qua: dispatch.ket_qua ?? '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((p) => ({ ...p, [k]: e.target.value }));

  // m40 — kết quả đã duyệt là bất biến: sửa phải đi đường tạo phiên bản mới kèm lý do.
  const approved = dispatch.result_approval_status === 'approved';
  const pending = dispatch.result_approval_status === 'pending';

  async function save() {
    setSaving(true);
    try {
      await flowApi.updateDispatchResult(dispatch.id, {
        don_vi: v.don_vi || null, phuong_phap: v.phuong_phap || null,
        ket_qua: v.ket_qua || null,
      });
      if (file) await flowApi.uploadIntakeFile('sample_dispatch', dispatch.id, file);
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  /** Lưu nội dung rồi gửi đi duyệt trong một lượt — quầy không phải bấm hai lần. */
  async function submitForApproval() {
    setSubmitting(true);
    try {
      await flowApi.updateDispatchResult(dispatch.id, {
        don_vi: v.don_vi || null, phuong_phap: v.phuong_phap || null,
        ket_qua: v.ket_qua || null,
      });
      if (file) await flowApi.uploadIntakeFile('sample_dispatch', dispatch.id, file);
      await flowApi.submitDispatchResult(dispatch.id);
      toast.success('Đã gửi kết quả đi duyệt — trưởng phòng sẽ phê duyệt');
      onDone();
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open onClose={onClose} title={`Kết quả — ${dispatch.chi_tieu}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving || submitting}>Đóng</Button>
          {!approved && (
            <>
              <Button variant="secondary" onClick={save} loading={saving} disabled={submitting}>
                Lưu nháp
              </Button>
              <Button onClick={submitForApproval} loading={submitting} disabled={saving}>
                Gửi duyệt
              </Button>
            </>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Trạng thái duyệt — nguồn là sample_results, không phải cờ trên phiếu. */}
        {approved && (
          <div className="rounded-lg border border-success/40 bg-success/10 p-2.5 text-sm text-ink">
            Kết quả <strong>đã được duyệt</strong>
            {dispatch.result_approved_by_name ? ` bởi ${dispatch.result_approved_by_name}` : ''}
            {dispatch.result_version ? ` (phiên bản ${dispatch.result_version})` : ''}. Không sửa
            trực tiếp được nữa — cần sửa thì tạo phiên bản mới kèm lý do.
          </div>
        )}
        {pending && (
          <div className="rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-sm text-ink">
            Đã gửi duyệt, <strong>đang chờ phê duyệt</strong>
            {dispatch.result_version ? ` (phiên bản ${dispatch.result_version})` : ''}.
          </div>
        )}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Đơn vị"><Input value={v.don_vi} onChange={set('don_vi')} disabled={approved} /></Field>
          {/* Chỉ hiển thị — người thực hiện là tài khoản đang đăng nhập, backend tự ghi. */}
          <Field
            label="Cán bộ phân tích"
            hint={dispatch.performed_by_name ? undefined : 'Ghi theo tài khoản của bạn khi lưu kết quả'}
          >
            <Input value={dispatch.performed_by_name ?? dispatch.can_bo ?? ''} readOnly disabled />
          </Field>
        </div>
        <Field label="Phương pháp thử"><Textarea value={v.phuong_phap} onChange={set('phuong_phap')} disabled={approved} /></Field>
        <Field label="Kết quả"><Textarea value={v.ket_qua} onChange={set('ket_qua')} disabled={approved} /></Field>

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
