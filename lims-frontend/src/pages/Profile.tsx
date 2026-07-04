import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { UserCircle, Save, RotateCcw, KeyRound, ShieldAlert } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { Avatar } from '@/components/ui/Avatar';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { ROLE_LABELS } from '@/types';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Hồ sơ cá nhân — người dùng tự cập nhật họ tên/email của chính mình.
 * Vai trò / phòng ban / trạng thái do Quản trị viên quản lý → chỉ hiển thị (read-only)
 * để tránh leo thang đặc quyền. Đổi mật khẩu nằm ở trang Cài đặt.
 */
export function Profile() {
  const { user, updateProfile } = useAuth();
  const toast = useToast();

  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [saving, setSaving] = useState(false);

  const dirty = useMemo(
    () =>
      fullName.trim() !== (user?.full_name ?? '') ||
      email.trim().toLowerCase() !== (user?.email ?? '').toLowerCase(),
    [fullName, email, user],
  );

  function reset() {
    setFullName(user?.full_name ?? '');
    setEmail(user?.email ?? '');
  }

  async function save() {
    const name = fullName.trim();
    const mail = email.trim();
    if (name.length < 1) return toast.error('Họ tên không được để trống');
    if (!EMAIL_RE.test(mail)) return toast.error('Email không hợp lệ');

    // chỉ gửi field thực sự thay đổi
    const body: { full_name?: string; email?: string } = {};
    if (name !== (user?.full_name ?? '')) body.full_name = name;
    if (mail.toLowerCase() !== (user?.email ?? '').toLowerCase()) body.email = mail;
    if (Object.keys(body).length === 0) return;

    setSaving(true);
    try {
      await updateProfile(body);
      toast.success('Cập nhật hồ sơ thành công');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hồ sơ cá nhân"
        description="Cập nhật thông tin tài khoản của bạn"
        icon={<UserCircle size={20} />}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Tóm tắt tài khoản */}
        <Card>
          <CardBody className="flex flex-col items-center gap-3 pt-5 text-center">
            <Avatar name={user?.full_name ?? '—'} size="lg" className="h-16 w-16 text-lg" />
            <div>
              <p className="text-base font-semibold text-ink">{user?.full_name ?? '—'}</p>
              <p className="text-sm text-subink">{user?.email ?? '—'}</p>
            </div>
            <div className="flex flex-wrap justify-center gap-1.5">
              <Badge tone="info">{user ? ROLE_LABELS[user.role] : '—'}</Badge>
              {user?.is_dept_lead && <Badge tone="warning">Trưởng nhóm</Badge>}
              <Badge tone={user?.status === 'active' ? 'success' : 'neutral'}>
                {user?.status === 'active' ? 'Đang hoạt động' : 'Vô hiệu hóa'}
              </Badge>
            </div>
            <div className="mt-1 w-full border-t border-hairline pt-3 text-sm">
              <Row label="Phòng ban" value={user?.department?.name ?? '—'} />
              <Row label="Tham gia" value={formatDate(user?.created_at)} />
            </div>
          </CardBody>
        </Card>

        {/* Form chỉnh sửa */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Thông tin cá nhân"
            subtitle="Họ tên và email hiển thị trên toàn hệ thống"
          />
          <CardBody className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Họ tên" required>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nguyễn Văn A"
                  maxLength={255}
                  autoComplete="name"
                />
              </Field>
              <Field label="Email" required hint="Dùng để đăng nhập">
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ban@lims.local"
                  autoComplete="email"
                />
              </Field>
            </div>

            {/* Field do admin quản lý — read-only */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Vai trò">
                <Input value={user ? ROLE_LABELS[user.role] : '—'} disabled />
              </Field>
              <Field label="Phòng ban">
                <Input value={user?.department?.name ?? '—'} disabled />
              </Field>
            </div>

            <p className="flex items-start gap-2 rounded-lg bg-plate px-3 py-2 text-xs text-subink">
              <ShieldAlert size={14} className="mt-0.5 shrink-0 text-stem" />
              Vai trò và phòng ban do Quản trị viên quản lý. Cần thay đổi, vui lòng liên hệ Quản trị viên.
            </p>

            <div className="flex items-center gap-2 border-t border-hairline pt-4">
              <Button onClick={save} loading={saving} disabled={!dirty}>
                <Save size={16} /> Lưu thay đổi
              </Button>
              <Button variant="secondary" onClick={reset} disabled={!dirty || saving}>
                <RotateCcw size={16} /> Hoàn tác
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Bảo mật → trỏ sang trang Cài đặt (không trùng lặp form đổi mật khẩu) */}
      <Card>
        <CardHeader title="Bảo mật" subtitle="Mật khẩu và quyền truy cập" />
        <CardBody>
          <Link
            to="/settings"
            className="inline-flex items-center gap-2 text-sm font-medium text-blueberry hover:underline"
          >
            <KeyRound size={16} /> Đổi mật khẩu & xem quyền tại trang Cài đặt
          </Link>
        </CardBody>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-0.5">
      <span className="shrink-0 text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}
