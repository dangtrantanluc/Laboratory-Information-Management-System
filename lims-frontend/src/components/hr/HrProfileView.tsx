import { useState } from 'react';
import { FileText, Wallet, History, GraduationCap, Plus, TrendingUp, Pencil, Paperclip } from 'lucide-react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/States';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { CompetenceKindBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { ApiError } from '@/lib/api';
import { formatDate, formatDecimal, formatMoney, daysUntil } from '@/lib/format';
import type { Competence, CompetenceKind, HrProfile } from '@/types';
import * as hrApi from '@/api/hr';
import * as usersApi from '@/api/users';

interface Props {
  userId: string;
  profile: HrProfile;
  onProfileChange: () => void;
  canManage: boolean;
  canEditSalary: boolean;
  canViewCompetence: boolean;
  canManageCompetence: boolean;
  selfView?: boolean;
  onNotFound?: () => void;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-2 text-sm">
      <span className="text-subink">{label}</span>
      <span className="text-right font-medium text-ink">{value ?? '—'}</span>
    </div>
  );
}

function DueBadge({ iso, warnWithin }: { iso?: string | null; warnWithin: number }) {
  if (!iso) return <span className="text-subink">Vô thời hạn / chưa đặt</span>;
  const days = daysUntil(iso);
  const tone = days < 0 ? 'overdue' : days <= warnWithin ? 'warning' : 'neutral';
  if (tone === 'neutral') return <span>{formatDate(iso)}</span>;
  return (
    <Badge tone={tone}>
      {formatDate(iso)}
      {days >= 0 ? ` · còn ${days} ngày` : ' · quá hạn'}
    </Badge>
  );
}

export function HrProfileView({
  userId,
  profile,
  onProfileChange,
  canManage,
  canEditSalary,
  canViewCompetence,
  canManageCompetence,
}: Props) {
  const hasSalary = 'computed_salary_amount' in profile || 'salary_coefficient' in profile;
  const hasContract = 'contract_signed_date' in profile || 'contract_type' in profile;
  const hasPII = 'id_number' in profile || 'dob' in profile || 'bank_account' in profile;

  const [contractOpen, setContractOpen] = useState(false);
  const [cycleOpen, setCycleOpen] = useState(false);
  const [raiseOpen, setRaiseOpen] = useState(false);

  return (
    <>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Thông tin chung */}
        <Card>
          <CardHeader title="Thông tin chung" />
          <CardBody className="divide-y divide-hairline pt-0">
            <Row label="Họ tên" value={profile.full_name} />
            <Row label="Email" value={profile.email ?? '—'} />
            <Row label="Phòng ban" value={profile.department_name ?? '—'} />
            <Row label="Chức danh" value={profile.job_title ?? '—'} />
            <Row label="Số điện thoại" value={profile.phone ?? '—'} />
            <Row label="Ngày vào làm" value={profile.hired_date ? formatDate(profile.hired_date) : '—'} />
            {hasPII && (
              <>
                <Row label="CMND/CCCD" value={profile.id_number ?? '—'} />
                <Row label="Ngày sinh" value={profile.dob ? formatDate(profile.dob) : '—'} />
                <Row label="Tài khoản NH" value={profile.bank_account ?? '—'} />
              </>
            )}
          </CardBody>
        </Card>

        {/* Hợp đồng */}
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <FileText size={15} className="text-stem" /> Hợp đồng
              </span>
            }
            action={
              hasContract && canManage ? (
                <Button size="sm" variant="secondary" onClick={() => setContractOpen(true)}>
                  <Pencil size={13} /> Cập nhật
                </Button>
              ) : undefined
            }
          />
          <CardBody className="pt-0">
            {hasContract ? (
              <div className="divide-y divide-hairline">
                <Row label="Loại HĐ" value={profile.contract_type ?? '—'} />
                <Row
                  label="Ngày ký"
                  value={profile.contract_signed_date ? formatDate(profile.contract_signed_date) : '—'}
                />
                <Row
                  label="Ngày hết hạn"
                  value={<DueBadge iso={profile.contract_end_date} warnWithin={30} />}
                />
                {!profile.contract_signed_date && canManage && (
                  <div className="pt-3">
                    <Button size="sm" variant="secondary" onClick={() => setContractOpen(true)}>
                      <Plus size={13} /> Thêm hợp đồng
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="py-3 text-sm text-subink">Không có quyền xem thông tin hợp đồng.</p>
            )}
          </CardBody>
        </Card>

        {/* Lương */}
        <Card>
          <CardHeader
            title={
              <span className="inline-flex items-center gap-2">
                <Wallet size={15} className="text-stem" /> Lương
              </span>
            }
            action={
              hasSalary && canEditSalary ? (
                <Button size="sm" onClick={() => setRaiseOpen(true)}>
                  <TrendingUp size={13} /> Nâng lương
                </Button>
              ) : undefined
            }
          />
          <CardBody className="pt-0">
            {hasSalary ? (
              <div className="divide-y divide-hairline">
                <Row label="Bậc/ngạch" value={profile.salary_grade ?? '—'} />
                <Row label="Hệ số" value={profile.salary_coefficient ? formatDecimal(profile.salary_coefficient, 2) : '—'} />
                <Row label="Lương cơ sở" value={formatMoney(profile.base_salary_amount, profile.currency ?? 'VND')} />
                <div className="flex justify-between gap-4 py-2 text-sm">
                  <span className="text-subink">Lương thực nhận</span>
                  <span className="text-right text-base font-bold text-blueberry">
                    {formatMoney(profile.computed_salary_amount, profile.currency ?? 'VND')}
                  </span>
                </div>
                <Row label="Lần nâng gần nhất" value={profile.last_salary_raise_date ? formatDate(profile.last_salary_raise_date) : '—'} />
                <div className="flex items-center justify-between gap-4 py-2 text-sm">
                  <span className="text-subink">Chu kỳ · kế tiếp</span>
                  <span className="flex items-center gap-2">
                    <Badge tone="neutral">{profile.salary_cycle_years ?? '—'} năm</Badge>
                    <DueBadge iso={profile.next_salary_raise_date} warnWithin={15} />
                  </span>
                </div>
                {canEditSalary && (
                  <div className="pt-3">
                    <Button size="sm" variant="ghost" onClick={() => setCycleOpen(true)}>
                      <Pencil size={13} /> Sửa chu kỳ nâng lương
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="py-3 text-sm text-subink">Bạn không có quyền xem thông tin lương của nhân sự này.</p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Lịch sử nâng lương */}
      {hasSalary && <SalaryHistorySection userId={userId} />}

      {/* Hồ sơ năng lực */}
      {canViewCompetence && (
        <CompetenceSection userId={userId} canManage={canManageCompetence} />
      )}

      {contractOpen && (
        <ContractModal
          userId={userId}
          profile={profile}
          onClose={() => setContractOpen(false)}
          onSaved={() => {
            setContractOpen(false);
            onProfileChange();
          }}
        />
      )}
      {cycleOpen && (
        <SalaryCycleModal
          userId={userId}
          current={profile.salary_cycle_years ?? 3}
          onClose={() => setCycleOpen(false)}
          onSaved={() => {
            setCycleOpen(false);
            onProfileChange();
          }}
        />
      )}
      {raiseOpen && (
        <SalaryRaiseModal
          userId={userId}
          profile={profile}
          onClose={() => setRaiseOpen(false)}
          onSaved={() => {
            setRaiseOpen(false);
            onProfileChange();
          }}
        />
      )}
    </>
  );
}

// ── Lịch sử nâng lương ──────────────────────────────────────────
function SalaryHistorySection({ userId }: { userId: string }) {
  const { data, loading } = useAsync(() => hrApi.listSalaryHistory(userId), [userId]);
  const items = data?.data ?? [];
  return (
    <Card>
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <History size={15} className="text-stem" /> Lịch sử nâng lương
          </span>
        }
        subtitle="Bản ghi chỉ ghi thêm (không sửa/xóa)"
      />
      <CardBody className="pt-0">
        {loading ? (
          <p className="py-3 text-sm text-subink">Đang tải…</p>
        ) : items.length === 0 ? (
          <p className="py-3 text-sm text-subink">Chưa có lần nâng lương nào.</p>
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-stem">
                  <th className="py-2 pr-4">Ngày</th>
                  <th className="py-2 pr-4">Bậc (cũ → mới)</th>
                  <th className="py-2 pr-4">Hệ số (cũ → mới)</th>
                  <th className="py-2 pr-4">Lương cơ sở (mới)</th>
                  <th className="py-2 pr-4">Người ghi</th>
                  <th className="py-2">Ghi chú</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {items.map((h) => (
                  <tr key={h.id}>
                    <td className="py-2.5 pr-4 font-medium text-ink">{formatDate(h.raise_date)}</td>
                    <td className="py-2.5 pr-4">
                      {h.old_grade ?? '—'} → <strong>{h.new_grade}</strong>
                    </td>
                    <td className="py-2.5 pr-4">
                      {h.old_coefficient ? formatDecimal(h.old_coefficient, 2) : '—'} →{' '}
                      <strong>{formatDecimal(h.new_coefficient, 2)}</strong>
                    </td>
                    <td className="py-2.5 pr-4">{formatMoney(h.new_base_amount)}</td>
                    <td className="py-2.5 pr-4 text-subink">{h.by_user_name ?? '—'}</td>
                    <td className="py-2.5 text-subink">{h.note ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ── Hồ sơ năng lực ──────────────────────────────────────────────
function CompetenceSection({ userId, canManage }: { userId: string; canManage: boolean }) {
  const toast = useToast();
  const { data, loading, reload } = useAsync(() => hrApi.listCompetences(userId), [userId]);
  const [createOpen, setCreateOpen] = useState(false);
  const items = data ?? [];

  return (
    <Card>
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <GraduationCap size={15} className="text-stem" /> Hồ sơ năng lực
          </span>
        }
        subtitle="Bằng cấp, chứng chỉ, ủy quyền thử nghiệm (VILAS §6.2)"
        action={
          canManage ? (
            <Button size="sm" variant="secondary" onClick={() => setCreateOpen(true)}>
              <Plus size={13} /> Thêm mục
            </Button>
          ) : undefined
        }
      />
      <CardBody className="pt-0">
        {loading ? (
          <p className="py-3 text-sm text-subink">Đang tải…</p>
        ) : items.length === 0 ? (
          <EmptyState title="Chưa có mục năng lực nào" />
        ) : (
          <div className="flex flex-col gap-2.5">
            {items.map((c) => (
              <CompetenceRow key={c.id} comp={c} canManage={canManage} onChanged={reload} />
            ))}
          </div>
        )}
      </CardBody>

      {createOpen && (
        <CompetenceModal
          userId={userId}
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm mục năng lực');
          }}
        />
      )}
    </Card>
  );
}

function CompetenceRow({
  comp,
  canManage,
  onChanged,
}: {
  comp: Competence;
  canManage: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [editOpen, setEditOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function onUpload(file: File) {
    setUploading(true);
    try {
      await hrApi.uploadCompetenceAttachment(comp.id, file);
      toast.success('Đã tải minh chứng');
      onChanged();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-hairline px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <CompetenceKindBadge kind={comp.kind} />
          <p className="font-semibold text-ink">{comp.title}</p>
          {comp.is_expired && <Badge tone="overdue">Hết hạn</Badge>}
        </div>
        <p className="mt-1 text-xs text-subink">
          {comp.issuer && `${comp.issuer} · `}
          {comp.issued_date && `Cấp ${formatDate(comp.issued_date)}`}
          {comp.expiry_date && ` · Hết hạn ${formatDate(comp.expiry_date)}`}
        </p>
        {comp.scope_detail && <p className="mt-1 text-xs text-ink">Phạm vi: {comp.scope_detail}</p>}
        {comp.authorized_by_name && (
          <p className="mt-0.5 text-xs text-subink">Người ủy quyền: {comp.authorized_by_name}</p>
        )}
      </div>
      {canManage && (
        <div className="flex shrink-0 items-center gap-1.5">
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-hairline px-2.5 py-1.5 text-xs text-stem hover:bg-plate">
            <Paperclip size={13} />
            {uploading ? 'Đang tải…' : comp.attachment_id ? 'Đổi minh chứng' : 'Minh chứng'}
            <input
              type="file"
              className="hidden"
              accept="application/pdf,image/png,image/jpeg"
              disabled={uploading}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUpload(f);
                e.target.value = '';
              }}
            />
          </label>
          <Button size="sm" variant="ghost" onClick={() => setEditOpen(true)}>
            <Pencil size={13} />
          </Button>
        </div>
      )}
      {editOpen && (
        <CompetenceModal
          userId=""
          competence={comp}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

// ── Modals ──────────────────────────────────────────────────────
function ContractModal({
  userId,
  profile,
  onClose,
  onSaved,
}: {
  userId: string;
  profile: HrProfile;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [signed, setSigned] = useState(profile.contract_signed_date ?? '');
  const [type, setType] = useState(profile.contract_type ?? '');
  const [end, setEnd] = useState(profile.contract_end_date ?? '');
  const [submitting, setSubmitting] = useState(false);
  const { data: types } = useAsync(() => hrApi.listContractTypes(), []);

  async function submit() {
    if (!signed) return toast.error('Chọn ngày ký hợp đồng');
    if (!type) return toast.error('Chọn loại hợp đồng');
    setSubmitting(true);
    try {
      await hrApi.updateContract(userId, {
        contract_signed_date: signed,
        contract_type: type,
        contract_end_date: end || null,
      });
      toast.success('Đã cập nhật hợp đồng');
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Cập nhật hợp đồng"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Ngày ký" required>
          <Input type="date" value={signed} onChange={(e) => setSigned(e.target.value)} />
        </Field>
        <Field label="Loại hợp đồng" required>
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">— Chọn —</option>
            {(types ?? []).map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ngày hết hạn" hint="Bỏ trống = hợp đồng vô thời hạn" className="sm:col-span-2">
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function SalaryCycleModal({
  userId,
  current,
  onClose,
  onSaved,
}: {
  userId: string;
  current: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [years, setYears] = useState(String(current));
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    const n = Number(years);
    if (!Number.isInteger(n) || n < 1) return toast.error('Chu kỳ phải là số nguyên ≥ 1');
    setSubmitting(true);
    try {
      await hrApi.updateSalaryCycle(userId, n);
      toast.success('Đã cập nhật chu kỳ nâng lương');
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Chu kỳ nâng lương"
      size="sm"
      description="Hệ thống tự tính lại ngày nâng lương kế tiếp."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Lưu
          </Button>
        </>
      }
    >
      <Field label="Số năm/chu kỳ" required>
        <Input type="number" min={1} step={1} value={years} onChange={(e) => setYears(e.target.value)} />
      </Field>
    </Modal>
  );
}

function SalaryRaiseModal({
  userId,
  profile,
  onClose,
  onSaved,
}: {
  userId: string;
  profile: HrProfile;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [grade, setGrade] = useState(profile.salary_grade ?? '');
  const [coefficient, setCoefficient] = useState(profile.salary_coefficient ?? '');
  const [base, setBase] = useState(profile.base_salary_amount ?? '');
  const [raiseDate, setRaiseDate] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!grade.trim()) return toast.error('Nhập bậc/ngạch');
    if (!coefficient.trim()) return toast.error('Nhập hệ số lương');
    if (!base.trim()) return toast.error('Nhập lương cơ sở');
    if (!raiseDate) return toast.error('Chọn ngày nâng lương');
    setSubmitting(true);
    try {
      await hrApi.createSalaryRaise(userId, {
        salary_grade: grade.trim(),
        salary_coefficient: coefficient.trim(),
        base_salary_amount: base.trim(),
        raise_date: raiseDate,
        note: note || null,
      });
      toast.success('Đã ghi nhận nâng lương');
      onSaved();
    } catch (err) {
      // 403 SALARY_FORBIDDEN → describeError trả message tiếng Việt
      if (err instanceof ApiError && err.code === 'SALARY_FORBIDDEN') {
        toast.error(describeError(err).title);
      } else {
        toast.error(describeError(err).title);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Ghi nhận nâng lương"
      description="Lương thực nhận = hệ số × lương cơ sở. Bản ghi sẽ được lưu vào lịch sử."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Ghi nhận
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Bậc/ngạch" required>
          <Input value={grade} onChange={(e) => setGrade(e.target.value)} placeholder="A1.4" />
        </Field>
        <Field label="Hệ số lương" required>
          <Input value={coefficient} onChange={(e) => setCoefficient(e.target.value)} inputMode="decimal" placeholder="3.99" />
        </Field>
        <Field label="Lương cơ sở" required>
          <Input value={base} onChange={(e) => setBase(e.target.value)} inputMode="decimal" placeholder="2340000" />
        </Field>
        <Field label="Ngày nâng lương" required>
          <Input type="date" value={raiseDate} onChange={(e) => setRaiseDate(e.target.value)} />
        </Field>
        <Field label="Ghi chú (số quyết định…)" className="sm:col-span-2">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="QĐ 123/2026" />
        </Field>
      </div>
    </Modal>
  );
}

function CompetenceModal({
  userId,
  competence,
  onClose,
  onSaved,
}: {
  userId: string;
  competence?: Competence;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!competence;
  const [kind, setKind] = useState<CompetenceKind>(competence?.kind ?? 'degree');
  const [title, setTitle] = useState(competence?.title ?? '');
  const [issuer, setIssuer] = useState(competence?.issuer ?? '');
  const [issued, setIssued] = useState(competence?.issued_date ?? '');
  const [expiry, setExpiry] = useState(competence?.expiry_date ?? '');
  const [scope, setScope] = useState(competence?.scope_detail ?? '');
  const [authorizedBy, setAuthorizedBy] = useState(competence?.authorized_by_user_id ?? '');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tên năng lực');
    if (kind === 'authorization' && !scope.trim())
      return toast.error('Ủy quyền cần nhập phạm vi/chỉ tiêu');
    if (kind === 'authorization' && !authorizedBy)
      return toast.error('Ủy quyền cần chọn người ủy quyền');
    setSubmitting(true);
    const body = {
      kind,
      title: title.trim(),
      issuer: issuer || null,
      issued_date: issued || null,
      expiry_date: expiry || null,
      scope_detail: kind === 'authorization' ? scope || null : null,
      authorized_by: kind === 'authorization' ? authorizedBy || null : null,
    };
    try {
      if (editing) await hrApi.updateCompetence(competence!.id, body);
      else await hrApi.createCompetence(userId, body);
      onSaved();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={editing ? 'Sửa mục năng lực' : 'Thêm mục năng lực'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            {editing ? 'Lưu' : 'Thêm'}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Loại" required>
          <Select value={kind} onChange={(e) => setKind(e.target.value as CompetenceKind)}>
            <option value="degree">Bằng cấp</option>
            <option value="certificate">Chứng chỉ</option>
            <option value="authorization">Ủy quyền thử nghiệm</option>
          </Select>
        </Field>
        <Field label="Nơi cấp / người cấp">
          <Input value={issuer} onChange={(e) => setIssuer(e.target.value)} />
        </Field>
        <Field label="Tên năng lực" required className="sm:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Thạc sĩ Hóa phân tích" />
        </Field>
        <Field label="Ngày cấp">
          <Input type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />
        </Field>
        <Field label="Ngày hết hạn">
          <Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
        </Field>
        {kind === 'authorization' && (
          <>
            <Field label="Phạm vi / chỉ tiêu được ủy quyền" required className="sm:col-span-2">
              <Textarea value={scope} onChange={(e) => setScope(e.target.value)} placeholder="Chỉ tiêu pH, phương pháp SOP-XX" />
            </Field>
            <Field label="Người ủy quyền" required className="sm:col-span-2">
              <Select value={authorizedBy} onChange={(e) => setAuthorizedBy(e.target.value)}>
                <option value="">— Chọn —</option>
                {(users?.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </Select>
            </Field>
          </>
        )}
      </div>
    </Modal>
  );
}
