/**
 * m35 — Danh bạ liên hệ của một khách hàng (1 khách – n người).
 *
 * Tách thành file riêng vì Customers.tsx là màn hình CRUD phẳng; nhét thêm một
 * bảng con có state tải/ghi riêng vào đó là trộn hai vòng đời dữ liệu khác nhau.
 *
 * HAI QUY TẮC NGHIỆP VỤ ĐƯỢC THỂ HIỆN Ở ĐÂY:
 *  - "Tắt" thay cho "xoá" với người nghỉ việc: phiếu cũ đã in tên họ, hồ sơ VILAS
 *    cần tra ngược được. Nút Xoá chỉ dành cho dòng nhập nhầm nên có xác nhận riêng.
 *  - Đúng MỘT liên hệ mặc định: backend tự gỡ cờ dòng cũ, UI chỉ cần gửi is_primary
 *    rồi tải lại — không tự suy diễn trạng thái ở client.
 */
import { useState } from 'react';
import { Check, Pencil, Plus, Star, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import type { CustomerContact } from '@/types';
import * as customersApi from '@/api/customers';

type Draft = { full_name: string; job_title: string; email: string; phone: string };
const EMPTY: Draft = { full_name: '', job_title: '', email: '', phone: '' };

export function CustomerContactsPanel({ customerId }: { customerId: string }) {
  const toast = useToast();
  const { data, loading, error, reload } = useAsync(
    () => customersApi.listCustomerContacts(customerId),
    [customerId],
  );
  const [draft, setDraft] = useState<Draft | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<CustomerContact | null>(null);

  const rows = data ?? [];
  const set = (k: keyof Draft) => (e: { target: { value: string } }) =>
    setDraft((p) => (p ? { ...p, [k]: e.target.value } : p));

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try {
      await fn();
      await reload();
      toast.success(ok);
      return true;
    } catch (err) {
      toast.error(describeError(err).title);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft?.full_name.trim()) return toast.error('Nhập họ tên người liên hệ');
    const body = {
      full_name: draft.full_name.trim(),
      job_title: draft.job_title || null,
      email: draft.email || null,
      phone: draft.phone || null,
    };
    const done = await run(
      () =>
        editingId
          ? customersApi.updateCustomerContact(customerId, editingId, body)
          : customersApi.createCustomerContact(customerId, body),
      editingId ? 'Đã cập nhật người liên hệ' : 'Đã thêm người liên hệ',
    );
    if (done) {
      setDraft(null);
      setEditingId(null);
    }
  }

  function startEdit(c: CustomerContact) {
    setEditingId(c.id);
    setDraft({
      full_name: c.full_name,
      job_title: c.job_title ?? '',
      email: c.email ?? '',
      phone: c.phone ?? '',
    });
  }

  if (loading) return <p className="text-sm text-subink">Đang tải danh bạ…</p>;
  if (error) return <p className="text-sm text-overdue">Không tải được danh bạ liên hệ.</p>;

  return (
    <div className="flex flex-col gap-3">
      {rows.length === 0 && !draft && (
        <p className="text-sm text-subink">
          Chưa có người liên hệ nào. Người đầu tiên thêm vào sẽ tự thành mặc định.
        </p>
      )}

      {rows.length > 0 && (
        <ul className="divide-y divide-hairline rounded-lg ring-1 ring-hairline">
          {rows.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-2 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={c.is_active ? 'font-semibold text-ink' : 'text-subink line-through'}>
                    {c.full_name}
                  </span>
                  {c.job_title && <span className="text-xs text-subink">· {c.job_title}</span>}
                  {c.is_primary && <Badge tone="success">Mặc định</Badge>}
                  {!c.is_active && <Badge tone="muted">Đã nghỉ</Badge>}
                </div>
                <div className="text-xs text-subink">
                  {[c.email, c.phone].filter(Boolean).join(' · ') || '—'}
                </div>
              </div>

              {/* Chỉ người CÒN hiệu lực mới được đặt mặc định — backend cũng chặn,
                  ẩn nút ở đây để nhân viên không bấm vào chỗ chắc chắn lỗi. */}
              {c.is_active && !c.is_primary && (
                <Button
                  variant="ghost" size="sm" disabled={busy}
                  onClick={() =>
                    run(
                      () => customersApi.updateCustomerContact(customerId, c.id, { is_primary: true }),
                      'Đã đặt làm liên hệ mặc định',
                    )
                  }
                >
                  <Star size={14} /> Đặt mặc định
                </Button>
              )}
              <Button
                variant="ghost" size="sm" disabled={busy}
                onClick={() =>
                  run(
                    () =>
                      customersApi.updateCustomerContact(customerId, c.id, {
                        is_active: !c.is_active,
                      }),
                    c.is_active ? 'Đã đánh dấu nghỉ việc' : 'Đã bật lại',
                  )
                }
              >
                {c.is_active ? <X size={14} /> : <Check size={14} />}
                {c.is_active ? 'Nghỉ việc' : 'Bật lại'}
              </Button>
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => startEdit(c)}>
                <Pencil size={14} /> Sửa
              </Button>
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => setRemoving(c)}>
                <Trash2 size={14} />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {draft ? (
        <div className="flex flex-col gap-3 rounded-lg bg-plate p-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Họ tên" required>
              <Input autoFocus value={draft.full_name} onChange={set('full_name')} />
            </Field>
            <Field label="Chức vụ">
              <Input value={draft.job_title} onChange={set('job_title')} placeholder="VD: Trưởng phòng QA" />
            </Field>
            <Field label="Email">
              <Input value={draft.email} onChange={set('email')} />
            </Field>
            <Field label="Điện thoại">
              <Input value={draft.phone} onChange={set('phone')} />
            </Field>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={save} loading={busy}>
              {editingId ? 'Lưu' : 'Thêm'}
            </Button>
            <Button
              variant="secondary" size="sm" disabled={busy}
              onClick={() => {
                setDraft(null);
                setEditingId(null);
              }}
            >
              Hủy
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button variant="secondary" size="sm" onClick={() => setDraft({ ...EMPTY })}>
            <Plus size={14} /> Thêm người liên hệ
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={async () => {
          const target = removing;
          if (!target) return;
          setRemoving(null);
          await run(
            () => customersApi.deleteCustomerContact(customerId, target.id),
            'Đã xoá người liên hệ',
          );
        }}
        title="Xoá người liên hệ?"
        message={
          `Xoá hẳn “${removing?.full_name ?? ''}” khỏi danh bạ. ` +
          'Nếu người này chỉ nghỉ việc, hãy dùng "Nghỉ việc" để giữ lịch sử cho phiếu cũ.'
        }
        confirmText="Xoá"
        loading={busy}
      />
    </div>
  );
}
