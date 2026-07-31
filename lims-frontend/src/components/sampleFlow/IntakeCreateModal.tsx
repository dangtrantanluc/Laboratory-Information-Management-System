/**
 * Modal "Nhận mẫu mới (BM 7.1.01)".
 *
 * Tách khỏi SampleFlow.tsx vì file đó đã chạm trần kích thước (xem
 * scripts/check-file-size.mjs — trần chỉ được HẠ, không được nới); form nhận mẫu
 * là một màn hình khép kín nên là ranh giới tách tự nhiên, cùng chỗ với
 * IntakeWorkflow đã có sẵn.
 */
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { CustomerPicker } from '@/components/ui/CustomerPicker';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { describeError } from '@/lib/errors';
import { canManageCustomers } from '@/lib/rbac';
import type { Customer, SampleIntake } from '@/types';
import * as flowApi from '@/api/sampleFlow';
import * as customersApi from '@/api/customers';

export function IntakeCreateModal({ onClose, onDone }: { onClose: () => void; onDone: (intake: SampleIntake) => void }) {
  const toast = useToast();
  const { user } = useAuth();
  const [f, setF] = useState({
    customer_name: '', address: '', tax_code: '', contact_person: '', phone: '', email: '',
    due_date: '', result_language: '', return_method: '', fee_note: '', description: '',
  });
  // m33 — khách trong sổ; null = vãng lai. Các ô trên là BẢN CHỤP của phiếu, sửa
  // đè không ghi ngược vào sổ (phiếu đã in phải giữ nguyên thông tin lúc nhận mẫu).
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [savingCustomer, setSavingCustomer] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((p) => ({ ...p, [k]: e.target.value }));

  /** Chọn khách trong sổ → tự điền 6 ô của BM 7.1.01. */
  function pickCustomer(c: Customer) {
    setCustomerId(c.id);
    setF((p) => ({
      ...p,
      customer_name: c.name,
      address: c.address ?? '',
      tax_code: c.tax_code ?? '',
      contact_person: c.contact_person ?? '',
      phone: c.phone ?? '',
      email: c.email ?? '',
    }));
  }

  /** Lưu những gì đã gõ trên phiếu thành khách mới trong sổ rồi liên kết luôn. */
  async function createCustomerFromForm() {
    if (!f.customer_name.trim()) return;
    setSavingCustomer(true);
    try {
      const c = await customersApi.createCustomer({
        name: f.customer_name.trim(),
        address: f.address || null,
        tax_code: f.tax_code || null,
        contact_person: f.contact_person || null,
        phone: f.phone || null,
        email: f.email || null,
      });
      setCustomerId(c.id);
      toast.success(`Đã thêm “${c.name}” vào sổ khách hàng`);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSavingCustomer(false);
    }
  }

  async function submit() {
    if (!f.customer_name.trim()) return toast.error('Nhập tên khách hàng');
    setSubmitting(true);
    try {
      const it = await flowApi.createIntake({
        customer_id: customerId,
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
        <Field
          label="Tên khách hàng / đơn vị"
          required
          hint="Chọn khách có sẵn trong sổ để tự điền địa chỉ, MST, người liên hệ, ĐT, mail."
        >
          <CustomerPicker
            autoFocus
            name={f.customer_name}
            customerId={customerId}
            onNameChange={(v) => {
              // Gõ tay ⇒ không còn là khách đã chọn nữa.
              setCustomerId(null);
              setF((p) => ({ ...p, customer_name: v }));
            }}
            onPick={pickCustomer}
            // Chỉ hiện nút thêm sổ cho người CÓ quyền: canManageIntake rộng hơn
            // canManageCustomers (lab_manager có intake:manage sẽ dính 403).
            onCreateNew={
              canManageCustomers(user) && !savingCustomer ? createCustomerFromForm : undefined
            }
          />
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
