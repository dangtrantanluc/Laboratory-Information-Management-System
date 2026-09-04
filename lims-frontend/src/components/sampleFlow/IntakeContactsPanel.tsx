/**
 * Người liên hệ theo VAI TRÒ trên một phiếu nhận mẫu (m43).
 *
 * Trước m43 phiếu chỉ giữ được MỘT người, nên hai câu hỏi mà quầy gặp hằng ngày
 * không trả lời được: *ai mang mẫu tới* và *kết quả giao cho ai* — khi đó là hai
 * người khác nhau.
 *
 * File riêng vì SampleFlow.tsx đang trong diện trần kích thước chuyển tiếp
 * (scripts/check-file-size.mjs — trần chỉ được HẠ), cùng chỗ với IntakeCreateModal
 * và DispatchResultModal đã tách trước đó.
 *
 * Bốn vai luôn hiện đủ, KHÔNG có nút "thêm dòng": danh sách vai là cố định, và để
 * trống một vai là câu trả lời hợp lệ ("người gửi cũng là người nhận kết quả").
 * Bắt quầy tự thêm từng dòng chỉ làm chậm thao tác mà không thêm thông tin gì.
 */
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { describeError } from '@/lib/errors';
import { CONTACT_ROLE_LABELS, type ContactRole, type IntakeContact } from '@/types';
import * as flowApi from '@/api/sampleFlow';

const ROLES: ContactRole[] = ['courier', 'technical', 'result_recipient', 'billing'];

const HINTS: Record<ContactRole, string> = {
  courier: 'Người trực tiếp mang mẫu đến quầy',
  technical: 'Người trả lời khi lab cần hỏi về nền mẫu / phương pháp',
  result_recipient: 'Người nhận phiếu kết quả — có thể khác người gửi mẫu',
  billing: 'Người nhận hoá đơn / đối chiếu công nợ',
};

type Row = { full_name: string; job_title: string; phone: string; email: string };
const EMPTY: Row = { full_name: '', job_title: '', phone: '', email: '' };

export function IntakeContactsPanel({
  intakeId, canEdit,
}: {
  intakeId: string; canEdit: boolean;
}) {
  const toast = useToast();
  const [rows, setRows] = useState<Record<ContactRole, Row>>(
    () => Object.fromEntries(ROLES.map((r) => [r, { ...EMPTY }])) as Record<ContactRole, Row>,
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    flowApi
      .listIntakeContacts(intakeId)
      .then((data) => {
        if (!alive) return;
        const next = Object.fromEntries(
          ROLES.map((r) => [r, { ...EMPTY }]),
        ) as Record<ContactRole, Row>;
        for (const c of data) {
          next[c.role] = {
            full_name: c.full_name ?? '', job_title: c.job_title ?? '',
            phone: c.phone ?? '', email: c.email ?? '',
          };
        }
        setRows(next);
      })
      // Danh sách liên hệ hỏng không được chặn phần còn lại của phiếu.
      .catch(() => {});
    return () => { alive = false; };
  }, [intakeId]);

  function set(role: ContactRole, key: keyof Row, value: string) {
    setRows((p) => ({ ...p, [role]: { ...p[role], [key]: value } }));
  }

  async function save() {
    setSaving(true);
    try {
      // Chỉ gửi vai ĐÃ ĐIỀN TÊN. Backend đặt lại cả bộ, nên bỏ trống một vai nghĩa
      // là xoá vai đó — đúng thứ người dùng vừa làm trên màn hình.
      const payload: IntakeContact[] = ROLES.filter((r) => rows[r].full_name.trim()).map((r) => ({
        role: r,
        full_name: rows[r].full_name.trim(),
        job_title: rows[r].job_title.trim() || null,
        phone: rows[r].phone.trim() || null,
        email: rows[r].email.trim() || null,
      }));
      await flowApi.setIntakeContacts(intakeId, payload);
      toast.success('Đã lưu người liên hệ');
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-subink">
        Để trống nếu cùng là một người. Thông tin lưu vào phiếu là <strong>bản chụp</strong> —
        sổ khách hàng đổi về sau không làm đổi phiếu này.
      </p>

      {ROLES.map((role) => (
        <div key={role} className="rounded-lg border border-hairline p-3">
          <div className="mb-2">
            <div className="text-sm font-semibold text-ink">{CONTACT_ROLE_LABELS[role]}</div>
            <div className="text-xs text-subink">{HINTS[role]}</div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
            <Field label="Họ tên">
              <Input
                value={rows[role].full_name}
                onChange={(e) => set(role, 'full_name', e.target.value)}
                disabled={!canEdit}
              />
            </Field>
            <Field label="Chức vụ">
              <Input
                value={rows[role].job_title}
                onChange={(e) => set(role, 'job_title', e.target.value)}
                disabled={!canEdit}
              />
            </Field>
            <Field label="Điện thoại">
              <Input
                value={rows[role].phone}
                onChange={(e) => set(role, 'phone', e.target.value)}
                disabled={!canEdit}
              />
            </Field>
            <Field label="Email">
              <Input
                value={rows[role].email}
                onChange={(e) => set(role, 'email', e.target.value)}
                disabled={!canEdit}
              />
            </Field>
          </div>
        </div>
      ))}

      {canEdit && (
        <div className="flex justify-end">
          <Button onClick={save} loading={saving}>Lưu người liên hệ</Button>
        </div>
      )}
    </div>
  );
}
