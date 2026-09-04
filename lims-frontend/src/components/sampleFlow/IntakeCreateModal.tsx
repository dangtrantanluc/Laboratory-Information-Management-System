/**
 * Modal "Nhận mẫu mới (BM 7.1.01)".
 *
 * Tách khỏi SampleFlow.tsx vì file đó đã chạm trần kích thước (xem
 * scripts/check-file-size.mjs — trần chỉ được HẠ, không được nới); form nhận mẫu
 * là một màn hình khép kín nên là ranh giới tách tự nhiên, cùng chỗ với
 * IntakeWorkflow đã có sẵn.
 */
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { CustomerPicker } from '@/components/ui/CustomerPicker';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { describeError } from '@/lib/errors';
import { canManageCustomers } from '@/lib/rbac';
import type { Customer, CustomerContact, SampleIntake } from '@/types';
import * as flowApi from '@/api/sampleFlow';
import * as customersApi from '@/api/customers';

export function IntakeCreateModal({ onClose, onDone }: { onClose: () => void; onDone: (intake: SampleIntake) => void }) {
  const toast = useToast();
  const { user } = useAuth();
  const [f, setF] = useState({
    // Mã số mẫu do nhân viên tự đặt — KHÔNG sinh sẵn, vì mã phải khớp nhãn đã
    // dán lên mẫu/sổ tay tại quầy nhận, không phải số thứ tự của hệ thống.
    code: '',
    customer_name: '', address: '', tax_code: '', contact_person: '', phone: '', email: '',
    due_date: '', result_language: '', return_method: '', fee_note: '', description: '',
    // m42 — việc đầu tiên nhân viên làm với mẫu vật lý: đếm và xem tình trạng.
    sample_count: '', condition_status: '', condition_note: '',
  });
  // m33 — khách trong sổ; null = vãng lai. Các ô trên là BẢN CHỤP của phiếu, sửa
  // đè không ghi ngược vào sổ (phiếu đã in phải giữ nguyên thông tin lúc nhận mẫu).
  const [customerId, setCustomerId] = useState<string | null>(null);
  // m35 — danh bạ của khách đã chọn. CHỈ người còn hiệu lực: không được điền tên
  // một người đã nghỉ việc lên phiếu mới.
  const [contacts, setContacts] = useState<CustomerContact[]>([]);
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

  /** Điền 3 ô liên hệ của phiếu từ một dòng danh bạ. */
  function applyContact(c: CustomerContact) {
    setF((p) => ({
      ...p,
      contact_person: c.full_name,
      phone: c.phone ?? '',
      email: c.email ?? '',
    }));
  }

  // Đổi khách → nạp danh bạ. Khách chỉ có 1 người thì điền luôn, KHÔNG bắt bấm chọn:
  // đa số khách rơi vào trường hợp này và quầy nhận mẫu không được chậm đi vì tính
  // năng phục vụ thiểu số.
  useEffect(() => {
    if (!customerId) {
      setContacts([]);
      return;
    }
    let alive = true;
    customersApi
      .listCustomerContacts(customerId, false)
      .then((rows) => {
        if (!alive) return;
        setContacts(rows);
        const primary = rows.find((r) => r.is_primary) ?? (rows.length === 1 ? rows[0] : undefined);
        if (primary) applyContact(primary);
      })
      // Danh bạ hỏng không được chặn việc nhận mẫu — phiếu vẫn gõ tay được.
      .catch(() => alive && setContacts([]));
    return () => {
      alive = false;
    };
  }, [customerId]);

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
    if (!f.code.trim()) return toast.error('Nhập mã số mẫu');
    if (!f.customer_name.trim()) return toast.error('Nhập tên khách hàng');
    // Nhận mẫu không đạt vẫn hợp lệ — nhưng phải bảo lưu trách nhiệm bằng mô tả.
    if (f.condition_status === 'not_acceptable' && !f.condition_note.trim()) {
      return toast.error('Mẫu không đạt: mô tả sai lệch (thiếu mẫu, sai bao bì, sai nhiệt độ…)');
    }
    setSubmitting(true);
    try {
      const it = await flowApi.createIntake({
        code: f.code.trim(),
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
        sample_count: f.sample_count ? Number(f.sample_count) : null,
        condition_status: f.condition_status || null,
        condition_note: f.condition_note || null,
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
      <FormBody>
        <FormSection title="Mã phiếu" cols={1}>
        <Field
          label="Mã số mẫu"
          required
          hint="Nhân viên tự đặt theo sổ nhận mẫu — trùng mã đã có sẽ bị từ chối."
        >
          <Input
            autoFocus
            value={f.code}
            onChange={set('code')}
            maxLength={32}
            placeholder="VD: NM-2026-0142"
          />
        </Field>
        </FormSection>

        <FormSection title="Khách hàng" cols={1}>
        <Field
          label="Tên khách hàng / đơn vị"
          required
          hint="Chọn khách có sẵn trong sổ để tự điền địa chỉ, MST, người liên hệ, ĐT, mail."
        >
          <CustomerPicker
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
        <Field label="Mail"><Input value={f.email} onChange={set('email')} /></Field>
        {/* Chỉ hiện khi khách có nhiều hơn 1 người liên hệ — 1 người thì đã tự điền,
            thêm một ô select chỉ làm quầy phải bấm thừa. */}
        {contacts.length > 1 && (
          <Field
            label="Chọn người liên hệ"
            hint="Điền nhanh 3 ô trên từ danh bạ của khách. Vẫn sửa tay được."
          >
            <Select
              value={contacts.find((c) => c.full_name === f.contact_person)?.id ?? ''}
              onChange={(e) => {
                const picked = contacts.find((c) => c.id === e.target.value);
                if (picked) applyContact(picked);
              }}
            >
              <option value="">— Gõ tay —</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}
                  {c.job_title ? ` · ${c.job_title}` : ''}
                  {c.is_primary ? ' (mặc định)' : ''}
                </option>
              ))}
            </Select>
          </Field>
        )}
        </FormSection>

        <FormSection title="Mẫu & hẹn trả" cols={1}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Số lượng mẫu nhận" hint="Đếm tại quầy, trước khi ký nhận.">
            <Input type="number" min={1} value={f.sample_count} onChange={set('sample_count')} />
          </Field>
          <Field
            label="Ngày hẹn trả kết quả"
            hint="Điền để hệ thống tính được mẫu quá hạn."
          >
            <Input value={f.due_date} onChange={set('due_date')} placeholder="dd/mm/yyyy" />
          </Field>
        </div>
        <Field label="Tình trạng mẫu">
          <Select value={f.condition_status} onChange={set('condition_status')}>
            <option value="">— Chưa đánh giá —</option>
            <option value="acceptable">Đạt điều kiện tiếp nhận</option>
            <option value="not_acceptable">KHÔNG đạt — nhận có bảo lưu</option>
          </Select>
        </Field>
        {/* Chỉ hiện khi cần: thêm một ô bắt buộc cho mọi phiếu là làm chậm quầy. */}
        {f.condition_status === 'not_acceptable' && (
          <Field
            label="Mô tả sai lệch"
            required
            hint="Thiếu mẫu · sai bao bì · mẫu hỏng · sai nhiệt độ bảo quản. Mẫu không đạt mà khách vẫn muốn làm thì phải ghi rõ để bảo lưu trách nhiệm."
          >
            <Textarea rows={2} value={f.condition_note} onChange={set('condition_note')} />
          </Field>
        )}
        <Field label="Mô tả mẫu">
          <Textarea value={f.description} onChange={set('description')} />
        </Field>
        </FormSection>

        <FormSection title="Kết quả & lệ phí" cols={1}>
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
        </FormSection>

        <FormSection title="Đính kèm" cols={1}>
        <Field label="Phiếu nhận mẫu đã điền (BM 7.1.01)">
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}
