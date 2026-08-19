import { useState } from 'react';
import { Presentation, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import {
  DescList,
  DescItem,
  DescLink,
  DescSection,
  DetailHero,
} from '@/components/ui/DescList';
import { Avatar } from '@/components/ui/Avatar';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { canManageResearch } from '@/lib/rbac';
import { TRAINING_LEVEL_LABELS } from '@/types';
import type { TeachingCourse, TrainingLevel } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

/** Sheet ĐÀO TẠO tách hai bảng cùng cấu trúc cột — HK3 là bổ sung của m34. */
const SEMESTERS = ['HK1', 'HK2', 'HK3'];

function levelLabel(v?: TrainingLevel | null): string {
  return v ? TRAINING_LEVEL_LABELS[v] : '—';
}

/** Tổng số tiết theo loại — cộng cả ba học kỳ (Excel để trống ô nghĩa là 0 tiết). */
function totalHours(c: TeachingCourse, kind: 'theory' | 'practice'): number {
  const k = kind === 'theory' ? 'theory' : 'practice';
  return (
    (c[`hk1_${k}_hours` as const] ?? 0) +
    (c[`hk2_${k}_hours` as const] ?? 0) +
    (c[`hk3_${k}_hours` as const] ?? 0)
  );
}

export function TeachingCourses() {
  const { user } = useAuth();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TeachingCourse | null>(null);
  const [viewTarget, setViewTarget] = useState<TeachingCourse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TeachingCourse | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(() => researchApi.listTeaching({ limit: 100 }), []);
  const canManage = canManageResearch(user);

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deleteTeaching(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<TeachingCourse>[] = [
    { key: 'course', header: 'Môn học', sortValue: (c) => c.course_name, render: (c) => <span className="font-semibold text-ink">{c.course_name}</span> },
    { key: 'user', header: 'Người phụ trách', render: (c) => c.user_name ?? '—' },
    { key: 'level', header: 'Bậc', render: (c) => (c.training_level ? <Badge tone="info">{levelLabel(c.training_level)}</Badge> : '—') },
    { key: 'year', header: 'Năm', align: 'center', sortValue: (c) => c.year, render: (c) => c.year },
    {
      // Excel có 3 cặp cột LT/TH theo học kỳ; bảng danh sách hiện tổng, chi tiết ở modal.
      key: 'hours',
      header: 'Tổng tiết (LT/TH)',
      align: 'center',
      sortValue: (c) => totalHours(c, 'theory') + totalHours(c, 'practice'),
      render: (c) => {
        const th = totalHours(c, 'theory');
        const pr = totalHours(c, 'practice');
        return th || pr ? <span className="tabular-nums">{th} / {pr}</span> : '—';
      },
    },
    {
      key: 'evidence',
      header: 'Minh chứng',
      align: 'center',
      render: (c) =>
        c.evidence_url ? (
          <a
            href={c.evidence_url}
            target="_blank"
            rel="noreferrer"
            className="text-berry hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            Xem
          </a>
        ) : (
          '—'
        ),
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (c: TeachingCourse) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(c)}>
                  <Pencil size={14} />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(c)}>
                  <Trash2 size={14} className="text-overdue" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Môn giảng dạy"
        description="Các môn học được phân công giảng dạy theo học kỳ"
        icon={<Presentation size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm môn
            </Button>
          )
        }
      />
      <Card>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(c) => c.id}
          loading={loading}
          pageSize={12}
          // Bấm hàng mở modal XEM, không nhảy thẳng vào form ghi: bảng chỉ hiện
          // TỔNG số tiết nên trước đây muốn xem tách HK1/HK2/HK3 buộc phải vào
          // chế độ sửa — vừa lệch với 6 trang cùng nhóm, vừa dễ sửa nhầm.
          onRowClick={(c) => setViewTarget(c)}
        />
      </Card>

      {viewTarget && (
        <TeachingDetailModal
          course={viewTarget}
          canManage={canManage}
          onClose={() => setViewTarget(null)}
          onEdit={() => {
            const c = viewTarget;
            setViewTarget(null);
            setEditTarget(c);
          }}
        />
      )}
      {createOpen && (
        <TeachingModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã thêm');
          }}
        />
      )}
      {editTarget && (
        <TeachingModal
          course={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
            toast.success('Đã cập nhật');
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa môn giảng dạy"
        message={`Xóa môn "${deleteTarget?.course_name}"?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function TeachingDetailModal({
  course: c,
  canManage,
  onClose,
  onEdit,
}: {
  course: TeachingCourse;
  canManage: boolean;
  onClose: () => void;
  onEdit: () => void;
}) {
  const theory = totalHours(c, 'theory');
  const practice = totalHours(c, 'practice');
  // Chỉ hiện học kỳ có khai giờ. Bày đủ ba dòng trong đó hai dòng trống làm người
  // đọc phải tự lọc — mà môn dạy cả ba kỳ là ngoại lệ, không phải thường lệ.
  const terms = ([1, 2, 3] as const)
    .map((i) => ({
      label: `HK${i}`,
      theory: c[`hk${i}_theory_hours` as const] ?? null,
      practice: c[`hk${i}_practice_hours` as const] ?? null,
    }))
    .filter((t) => t.theory !== null || t.practice !== null);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={c.course_name}
      description="Môn học được phân công giảng dạy"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Đóng
          </Button>
          {canManage && (
            <Button onClick={onEdit}>
              <Pencil size={14} /> Chỉnh sửa
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-6">
        <DetailHero
          chips={
            <>
              {c.training_level && <Badge tone="info">{levelLabel(c.training_level)}</Badge>}
              {c.semester && <Badge tone="neutral">{c.semester}</Badge>}
            </>
          }
          metricLabel="Tổng tiết (LT / TH)"
          metric={theory || practice ? `${theory} / ${practice}` : null}
        />

        <DescSection title="Số tiết theo học kỳ">
          {terms.length === 0 ? (
            <p className="text-sm text-stem">Chưa khai số tiết cho học kỳ nào.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[320px] border-collapse text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-stem">
                    <th className="pb-2 pr-4 font-semibold">Học kỳ</th>
                    <th className="pb-2 pr-4 font-semibold">Lý thuyết</th>
                    <th className="pb-2 font-semibold">Thực hành</th>
                  </tr>
                </thead>
                <tbody>
                  {terms.map((t) => (
                    <tr key={t.label} className="border-t border-hairline">
                      <td className="py-2 pr-4 font-medium text-ink">{t.label}</td>
                      <td className="py-2 pr-4 tabular-nums text-ink">{t.theory ?? '—'}</td>
                      <td className="py-2 tabular-nums text-ink">{t.practice ?? '—'}</td>
                    </tr>
                  ))}
                  <tr className="border-t border-hairline-hi">
                    <td className="py-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-stem">
                      Tổng
                    </td>
                    <td className="py-2 pr-4 font-semibold tabular-nums text-ink">{theory}</td>
                    <td className="py-2 font-semibold tabular-nums text-ink">{practice}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </DescSection>

        <DescSection title="Giảng viên & minh chứng">
          <DescList>
            <DescItem
              label="Giảng viên"
              value={
                c.user_name ? (
                  <span className="inline-flex items-center gap-2">
                    <Avatar name={c.user_name} size="sm" />
                    <span>
                      {c.user_name}
                      {!c.user_id && <span className="ml-1.5 text-xs text-stem">(thỉnh giảng)</span>}
                    </span>
                  </span>
                ) : null
              }
            />
            <DescItem label="Phòng ban" value={c.department_name} />
            <DescItem label="Năm" value={c.year} />
            <DescItem label="Năm học" value={c.academic_year} />
            <DescLink url={c.evidence_url} label="Link minh chứng (thời khoá biểu)" />
            <DescItem full label="Ghi chú" value={c.note} />
          </DescList>
        </DescSection>
      </div>
    </Modal>
  );
}

function TeachingModal({
  course,
  onClose,
  onSaved,
}: {
  course?: TeachingCourse;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const editing = !!course;

  // Giảng viên: nội bộ HOẶC thỉnh giảng ngoài hệ thống (XOR, khớp ck_tc_lecturer_xor).
  const [mode, setMode] = useState<'internal' | 'external'>(
    course && !course.user_id ? 'external' : 'internal',
  );
  const [userId, setUserId] = useState(course?.user_id ?? user?.id ?? '');
  const [externalName, setExternalName] = useState(course?.lecturer_external_name ?? '');

  const [courseName, setCourseName] = useState(course?.course_name ?? '');
  const [trainingLevel, setTrainingLevel] = useState<string>(course?.training_level ?? '');
  const [semester, setSemester] = useState(course?.semester ?? '');
  const [year, setYear] = useState(String(course?.year ?? new Date().getFullYear()));
  const [academicYear, setAcademicYear] = useState(course?.academic_year ?? '');
  // Sáu ô số tiết: 3 học kỳ × (lý thuyết, thực hành) — đúng cấu trúc sheet ĐÀO TẠO.
  const [hours, setHours] = useState<Record<string, string>>({
    hk1_theory_hours: course?.hk1_theory_hours?.toString() ?? '',
    hk1_practice_hours: course?.hk1_practice_hours?.toString() ?? '',
    hk2_theory_hours: course?.hk2_theory_hours?.toString() ?? '',
    hk2_practice_hours: course?.hk2_practice_hours?.toString() ?? '',
    hk3_theory_hours: course?.hk3_theory_hours?.toString() ?? '',
    hk3_practice_hours: course?.hk3_practice_hours?.toString() ?? '',
  });
  const [note, setNote] = useState(course?.note ?? '');
  const [evidenceUrl, setEvidenceUrl] = useState(course?.evidence_url ?? '');
  const [submitting, setSubmitting] = useState(false);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);

  function setHour(key: string, value: string) {
    setHours((prev) => ({ ...prev, [key]: value }));
  }

  /** '' → null (không khai), số → number. Giữ 0 là giá trị hợp lệ. */
  function hourValue(key: string): number | null {
    const raw = hours[key];
    if (raw === '') return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  function invalidHour(): string | null {
    for (const [key, raw] of Object.entries(hours)) {
      if (raw === '') continue;
      const n = Number(raw);
      if (!Number.isInteger(n) || n < 0 || n > 10000) {
        return `Số tiết "${key}" phải là số nguyên từ 0 đến 10000`;
      }
    }
    return null;
  }

  async function submit() {
    if (!courseName.trim()) return toast.error('Nhập tên môn');
    if (mode === 'internal' && !userId) return toast.error('Chọn giảng viên');
    if (mode === 'external' && !externalName.trim()) return toast.error('Nhập tên giảng viên thỉnh giảng');
    const y = Number(year);
    if (!Number.isInteger(y)) return toast.error('Năm không hợp lệ');
    const hourErr = invalidHour();
    if (hourErr) return toast.error(hourErr);

    const shared = {
      course_name: courseName.trim(),
      semester: semester || null,
      year: y,
      academic_year: academicYear.trim() || null,
      training_level: (trainingLevel || null) as TrainingLevel | null,
      hk1_theory_hours: hourValue('hk1_theory_hours'),
      hk1_practice_hours: hourValue('hk1_practice_hours'),
      hk2_theory_hours: hourValue('hk2_theory_hours'),
      hk2_practice_hours: hourValue('hk2_practice_hours'),
      hk3_theory_hours: hourValue('hk3_theory_hours'),
      hk3_practice_hours: hourValue('hk3_practice_hours'),
      note: note.trim() || null,
      evidence_url: evidenceUrl.trim() || null,
    };

    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateTeaching(course!.id, shared);
      } else {
        await researchApi.createTeaching({
          ...shared,
          user_id: mode === 'internal' ? userId : null,
          lecturer_external_name: mode === 'external' ? externalName.trim() : null,
        });
      }
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
      size="lg"
      title={editing ? 'Sửa môn giảng dạy' : 'Thêm môn giảng dạy'}
      description="Số tiết khai theo từng học kỳ; để trống ô nào nghĩa là học kỳ đó không dạy."
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
      <FormBody>
        <FormSection title="Môn học & giảng viên">
          {!editing && (
            <>
              <Field label="Giảng viên" required>
                <Select value={mode} onChange={(e) => setMode(e.target.value as 'internal' | 'external')}>
                  <option value="internal">Trong hệ thống</option>
                  <option value="external">Thỉnh giảng (ngoài hệ thống)</option>
                </Select>
              </Field>
              {mode === 'internal' ? (
                <Field label="Chọn người" required>
                  <Select value={userId} onChange={(e) => setUserId(e.target.value)}>
                    <option value="">— Chọn —</option>
                    {(users?.data ?? []).map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : (
                <Field label="Họ tên giảng viên" required>
                  <Input value={externalName} onChange={(e) => setExternalName(e.target.value)} />
                </Field>
              )}
            </>
          )}

          <Field label="Tên môn" required className="md:col-span-2">
            <Input value={courseName} onChange={(e) => setCourseName(e.target.value)} />
          </Field>

          <Field label="Bậc đào tạo">
            <Select value={trainingLevel} onChange={(e) => setTrainingLevel(e.target.value)}>
              <option value="">— Chưa phân loại —</option>
              {Object.entries(TRAINING_LEVEL_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Học kỳ chính" hint="Tuỳ chọn — một môn có thể dạy nhiều kỳ">
            <Select value={semester} onChange={(e) => setSemester(e.target.value)}>
              <option value="">— Không ghi —</option>
              {SEMESTERS.map((sm) => (
                <option key={sm} value={sm}>
                  {sm}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Năm" required>
            <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
          </Field>
          <Field label="Năm học">
            <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" />
          </Field>
        </FormSection>

        <FormSection title="Số tiết theo học kỳ" cols={1}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[360px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-subink">
                  <th className="pb-2 pr-3 font-medium">Học kỳ</th>
                  <th className="pb-2 pr-3 font-medium">Lý thuyết</th>
                  <th className="pb-2 font-medium">Thực hành</th>
                </tr>
              </thead>
              <tbody>
                {SEMESTERS.map((sm, i) => (
                  <tr key={sm}>
                    <td className="py-1.5 pr-3 font-medium text-ink">{sm}</td>
                    <td className="py-1.5 pr-3">
                      <Input
                        type="number"
                        min={0}
                        aria-label={`Số tiết lý thuyết ${sm}`}
                        value={hours[`hk${i + 1}_theory_hours`]}
                        onChange={(e) => setHour(`hk${i + 1}_theory_hours`, e.target.value)}
                      />
                    </td>
                    <td className="py-1.5">
                      <Input
                        type="number"
                        min={0}
                        aria-label={`Số tiết thực hành ${sm}`}
                        value={hours[`hk${i + 1}_practice_hours`]}
                        onChange={(e) => setHour(`hk${i + 1}_practice_hours`, e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </FormSection>

        <FormSection title="Minh chứng & ghi chú">
          <Field label="Link minh chứng" hint="Thời khoá biểu — Drive, SharePoint…" className="md:col-span-2">
            <Input value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} placeholder="https://" />
          </Field>
          <Field label="Ghi chú" className="md:col-span-2">
            <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}
