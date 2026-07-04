import { useState } from 'react';
import { Settings as SettingsIcon, KeyRound, ShieldCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Input } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { describeError } from '@/lib/errors';
import { ROLE_LABELS } from '@/types';

export function Settings() {
  const { user, changePassword } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submitPwd() {
    if (next.length < 8) return toast.error('Mật khẩu mới tối thiểu 8 ký tự');
    if (next !== confirm) return toast.error('Xác nhận mật khẩu không khớp');
    setSubmitting(true);
    try {
      await changePassword(current, next);
      toast.success('Đổi mật khẩu thành công');
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Cài đặt & Tài khoản" description="Thông tin tài khoản, đổi mật khẩu, quyền" icon={<SettingsIcon size={20} />} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="Thông tin tài khoản" />
          <CardBody className="flex flex-col gap-2.5 text-sm">
            <Row label="Họ tên" value={user?.full_name ?? '—'} />
            <Row label="Email" value={user?.email ?? '—'} />
            <Row label="Vai trò" value={user ? ROLE_LABELS[user.role] : '—'} />
            <Row label="Phòng ban" value={user?.department?.name ?? '—'} />
            <div className="flex justify-between gap-4">
              <span className="text-subink">Trưởng nhóm</span>
              <Badge tone={user?.is_dept_lead ? 'info' : 'neutral'}>{user?.is_dept_lead ? 'Có' : 'Không'}</Badge>
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Đổi mật khẩu" subtitle="Cập nhật mật khẩu đăng nhập" />
          <CardBody>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Mật khẩu hiện tại">
                <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
              </Field>
              <Field label="Mật khẩu mới">
                <Input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
              </Field>
              <Field label="Xác nhận">
                <Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
              </Field>
            </div>
            <div className="mt-4">
              <Button onClick={submitPwd} loading={submitting}>
                <KeyRound size={16} /> Đổi mật khẩu
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Ma trận quyền của bạn"
          subtitle="Các quyền hiệu lực (đọc từ vai trò + trưởng nhóm)"
        />
        <CardBody>
          {(user?.permissions ?? []).length === 0 ? (
            <p className="text-sm text-subink">Không có quyền nào.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(user?.permissions ?? []).map((p, i) => (
                <Badge key={i} tone="neutral" className="gap-1">
                  <ShieldCheck size={12} /> {p.resource}:{p.action}
                  {p.scope ? ` (${p.scope})` : ''}
                </Badge>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="shrink-0 text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}
