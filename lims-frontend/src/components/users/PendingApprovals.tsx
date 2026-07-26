import { useState } from 'react';
import { UserCheck, MailWarning, CheckCircle2, XCircle } from 'lucide-react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Field, Select, Textarea } from '@/components/ui/Field';
import { FormGrid } from '@/components/ui/FormGrid';
import { LoadingState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import { ROLE_LABELS, type Role, type UserListItem } from '@/types';
import * as usersApi from '@/api/users';

const ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as Role[]).map((r) => ({
  value: r,
  label: ROLE_LABELS[r],
}));

/**
 * Hàng chờ duyệt tài khoản tự đăng ký (m30).
 *
 * Vai trò do Quản trị viên chọn Ở ĐÂY, không phải do người đăng ký khai — đó là
 * điểm mấu chốt khiến việc mở đăng ký công khai vẫn an toàn với ISO/IEC 17025.
 */
export function PendingApprovals({ onChanged }: { onChanged?: () => void }) {
  const toast = useToast();
  const { data, loading, reload } = useAsync(
    () => usersApi.listUsers({ status: 'pending', limit: 50 }),
    [],
  );
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);
  const [approving, setApproving] = useState<UserListItem | null>(null);
  const [rejecting, setRejecting] = useState<UserListItem | null>(null);

  const pending = data?.data ?? [];

  function afterChange() {
    reload();
    onChanged?.();
  }

  if (!loading && pending.length === 0) return null; // không có gì chờ → ẩn hẳn khối

  return (
    <>
      <Card className="border-pending/30">
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <UserCheck size={16} className="text-pending" />
              Tài khoản chờ duyệt
              {pending.length > 0 && <Badge tone="pending">{pending.length}</Badge>}
            </span>
          }
          subtitle="Người dùng tự đăng ký — cần gán vai trò và phòng ban trước khi kích hoạt"
        />
        <CardBody className="p-0">
          {loading ? (
            <LoadingState label="Đang tải danh sách chờ…" />
          ) : (
            <ul className="divide-y divide-hairline">
              {pending.map((u) => {
                const verified = !!u.email_verified_at;
                return (
                  <li
                    key={u.id}
                    className="flex flex-col gap-3 px-5 py-3.5 md:flex-row md:items-center"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">{u.full_name}</p>
                      <p className="text-xs text-subink">{u.email}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-stem">
                        <span>Đăng ký {formatDateTime(u.created_at)}</span>
                        {verified ? (
                          <Badge tone="success">
                            <CheckCircle2 size={11} /> Đã xác thực email
                          </Badge>
                        ) : (
                          <Badge tone="warning">
                            <MailWarning size={11} /> Chưa xác thực email
                          </Badge>
                        )}
                      </p>
                    </div>

                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        size="sm"
                        disabled={!verified}
                        title={
                          verified
                            ? undefined
                            : 'Người dùng chưa bấm liên kết xác thực trong thư — chưa thể duyệt'
                        }
                        onClick={() => setApproving(u)}
                      >
                        <CheckCircle2 size={14} /> Duyệt
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-overdue hover:bg-overdue/10"
                        onClick={() => setRejecting(u)}
                      >
                        <XCircle size={14} /> Từ chối
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>

      {approving && (
        <ApproveModal
          user={approving}
          departments={depts?.data ?? []}
          onClose={() => setApproving(null)}
          onDone={() => {
            setApproving(null);
            toast.success('Đã duyệt tài khoản — hệ thống đã gửi thư thông báo');
            afterChange();
          }}
        />
      )}

      {rejecting && (
        <RejectModal
          user={rejecting}
          onClose={() => setRejecting(null)}
          onDone={() => {
            setRejecting(null);
            toast.success('Đã từ chối yêu cầu mở tài khoản');
            afterChange();
          }}
        />
      )}
    </>
  );
}

function ApproveModal({
  user,
  departments,
  onClose,
  onDone,
}: {
  user: UserListItem;
  departments: { id: string; name: string }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [role, setRole] = useState<Role>('staff');
  const [departmentId, setDepartmentId] = useState('');
  const [isDeptLead, setIsDeptLead] = useState(false);
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await usersApi.approveUser(user.id, {
        role,
        department_id: departmentId || null,
        is_dept_lead: isDeptLead,
      });
      onDone();
    } catch (err) {
      const { title, description } = describeError(err);
      toast.error(title, description);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Duyệt tài khoản"
      description={`${user.full_name} · ${user.email}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button onClick={submit} loading={saving}>
            <CheckCircle2 size={16} /> Duyệt &amp; kích hoạt
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="rounded-lg bg-plate p-3 text-xs text-subink">
          Vai trò và phòng ban bạn chọn ở đây quyết định quyền truy cập của người dùng. Người
          đăng ký không tự khai được các thông tin này.
        </p>

        <FormGrid>
          <Field label="Vai trò" required>
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Phòng ban" hint="Để trống nếu chưa xác định">
            <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">— Chưa gán —</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
        </FormGrid>

        {departmentId && (
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={isDeptLead}
              onChange={(e) => setIsDeptLead(e.target.checked)}
            />
            Đặt làm trưởng phòng ban này
          </label>
        )}
      </div>
    </Modal>
  );
}

function RejectModal({
  user,
  onClose,
  onDone,
}: {
  user: UserListItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (reason.trim().length < 3) return toast.error('Vui lòng nhập lý do từ chối');
    setSaving(true);
    try {
      await usersApi.rejectUser(user.id, reason.trim());
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Từ chối yêu cầu mở tài khoản"
      description={`${user.full_name} · ${user.email}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button variant="danger" onClick={submit} loading={saving}>
            Từ chối
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-subink">
          Lý do sẽ được gửi tới người dùng qua email. Bản ghi vẫn được giữ lại để phục vụ truy
          vết theo ISO/IEC 17025.
        </p>
        <Field label="Lý do từ chối" required>
          <Textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="VD: Không thuộc nhân sự của Viện; vui lòng liên hệ Văn phòng."
          />
        </Field>
      </div>
    </Modal>
  );
}
