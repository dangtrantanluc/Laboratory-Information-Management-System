import { useState } from 'react';
import { FolderKanban, Plus, Pencil, Trash2, Users2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  DescList,
  DescItem,
  DescLink,
  DescPeople,
  DescPeriod,
  DescSection,
  DetailHero,
} from '@/components/ui/DescList';
import { Avatar } from '@/components/ui/Avatar';
import { Field, Input, Select } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import {
  ContributorEditor,
  emptyContributor,
  toMembers,
  validateContributors,
  type ContributorRow,
} from '@/components/hr/ContributorEditor';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { formatDate, formatMoney } from '@/lib/format';
import { canManageResearch } from '@/lib/rbac';
import type { ResearchProject } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

// Trạng thái đề tài → nhãn + màu badge (dễ quét trong bảng)
const PROJECT_STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  ongoing: { label: 'Đang thực hiện', tone: 'pending' },
  completed: { label: 'Hoàn thành', tone: 'success' },
  accepted: { label: 'Đã nghiệm thu', tone: 'info' },
  cancelled: { label: 'Đã hủy', tone: 'muted' },
};
function ProjectStatusBadge({ status }: { status: string }) {
  const s = PROJECT_STATUS[status] ?? { label: status, tone: 'neutral' as BadgeTone };
  return <Badge tone={s.tone} dot>{s.label}</Badge>;
}

export function ResearchProjects() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [level, setLevel] = useState('');
  const [editTarget, setEditTarget] = useState<ResearchProject | null>(null);
  const [viewTarget, setViewTarget] = useState<ResearchProject | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ResearchProject | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => researchApi.listProjects({ q: dq || undefined, level: level || undefined, limit: 100 }),
    [dq, level],
  );
  const { data: levels } = useAsync(() => researchApi.listProjectLevels(), []);
  const canManage = canManageResearch(user);

  const levelLabel = (code: string) => (levels ?? []).find((l) => l.code === code)?.label ?? code;

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deleteProject(deleteTarget.id);
      toast.success('Đã xóa đề tài');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<ResearchProject>[] = [
    {
      key: 'title',
      header: 'Đề tài',
      sortValue: (p) => p.title,
      render: (p) => (
        <div>
          <p className="font-semibold text-ink">{p.title}</p>
          <p className="text-xs text-subink">{p.code ?? ''}</p>
        </div>
      ),
    },
    { key: 'level', priority: 1, header: 'Cấp', render: (p) => <Badge tone="info">{levelLabel(p.level)}</Badge> },
    { key: 'lead', header: 'Chủ nhiệm', render: (p) => p.lead_user_name ?? '—' },
    { key: 'department', header: 'Phòng', render: (p) => p.department_name ?? '—' },
    {
      key: 'members',
      header: 'Thành viên',
      align: 'center',
      render: (p) => (
        <span className="inline-flex items-center gap-1 text-subink">
          <Users2 size={13} /> {p.member_count ?? p.members?.length ?? 0}
        </span>
      ),
    },
    { key: 'status', priority: 1, header: 'Trạng thái', render: (p) => <ProjectStatusBadge status={p.status} /> },
    {
      key: 'time',
      header: 'Thời gian',
      render: (p) => `${p.start_date ? formatDate(p.start_date) : '—'} → ${p.end_date ? formatDate(p.end_date) : '—'}`,
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (p: ResearchProject) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => setEditTarget(p)}>
                  <Pencil size={14} />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(p)}>
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
        title="Đề tài NCKH"
        description="Quản lý đề tài nghiên cứu khoa học và thành viên tham gia"
        icon={<FolderKanban size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm đề tài
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tên đề tài…" className="w-full sm:max-w-xs sm:flex-1" />
          <Select value={level} onChange={(e) => setLevel(e.target.value)} className="w-full sm:max-w-[200px]">
            <option value="">Mọi cấp</option>
            {(levels ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(p) => p.id}
          loading={loading}
          pageSize={12}
          onRowClick={(p) => setViewTarget(p)}
        />
      </Card>

      {createOpen && (
        <ProjectModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã tạo đề tài');
          }}
        />
      )}
      {editTarget && (
        <ProjectModal
          project={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
            toast.success('Đã cập nhật đề tài');
          }}
        />
      )}
      {viewTarget && (
        <ProjectDetailModal
          project={viewTarget}
          levelLabel={levelLabel}
          canManage={canManage}
          onClose={() => setViewTarget(null)}
          onEdit={() => {
            const p = viewTarget;
            setViewTarget(null);
            setEditTarget(p);
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={doDelete}
        title="Xóa đề tài"
        message={`Xóa đề tài "${deleteTarget?.title}"? Thao tác không thể hoàn tác.`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function ProjectDetailModal({
  project,
  levelLabel,
  canManage,
  onClose,
  onEdit,
}: {
  project: ResearchProject;
  levelLabel: (code: string) => string;
  canManage: boolean;
  onClose: () => void;
  onEdit: () => void;
}) {
  // Tải chi tiết để chắc chắn có danh sách thành viên (list có thể chỉ trả member_count).
  const { data, loading } = useAsync(() => researchApi.getProject(project.id), [project.id]);
  const p = data ?? project;
  const members = p.members ?? [];

  const people = members.map((m) => ({
    name: m.name ?? m.external_name ?? 'Không rõ',
    role: m.role_in_project === 'lead' ? 'Chủ nhiệm' : null,
    external: !m.user_id,
  }));

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={p.title}
      description={p.code ? `Mã đề tài: ${p.code}` : 'Đề tài nghiên cứu khoa học'}
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
              <ProjectStatusBadge status={p.status} />
              <Badge tone="info">{levelLabel(p.level)}</Badge>
              {p.is_transferred && <Badge tone="success">Có chuyển giao</Badge>}
            </>
          }
          metricLabel="Kinh phí"
          metric={p.budget_amount ? formatMoney(p.budget_amount, p.budget_currency ?? 'VND') : null}
        />

        <DescSection title="Chủ trì & thời gian">
          <DescList>
            <DescItem
              label="Chủ nhiệm"
              value={
                p.lead_user_name ? (
                  <span className="inline-flex items-center gap-2">
                    <Avatar name={p.lead_user_name} size="sm" />
                    <span>
                      {p.lead_user_name}
                      {!p.lead_user_id && (
                        <span className="ml-1.5 text-xs text-stem">(ngoài hệ thống)</span>
                      )}
                    </span>
                  </span>
                ) : null
              }
            />
            <DescItem label="Phòng ban" value={p.department_name} />
            <DescPeriod label="Thời gian thực hiện" from={p.start_date} to={p.end_date} />
            <DescItem label="Năm học" value={p.academic_year} />
          </DescList>
        </DescSection>

        {(p.is_transferred || p.transfer_product) && (
          <DescSection title="Chuyển giao">
            <DescList cols={1}>
              <DescItem label="Sản phẩm chuyển giao" value={p.transfer_product} />
            </DescList>
          </DescSection>
        )}

        <DescSection title="Thành viên & minh chứng">
          <DescList>
            {loading ? (
              <DescItem full label="Thành viên tham gia" value="Đang tải…" />
            ) : (
              <DescPeople label="Thành viên tham gia" people={people} />
            )}
            <DescLink url={p.evidence_url} />
          </DescList>
        </DescSection>
      </div>
    </Modal>
  );
}

function ProjectModal({
  project,
  onClose,
  onSaved,
}: {
  project?: ResearchProject;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!project;
  const [title, setTitle] = useState(project?.title ?? '');
  const [code, setCode] = useState(project?.code ?? '');
  const [level, setLevel] = useState(project?.level ?? '');
  const [leadUserId, setLeadUserId] = useState(project?.lead_user_id ?? '');
  const [departmentId, setDepartmentId] = useState(project?.department_id ?? '');
  const [start, setStart] = useState(project?.start_date ?? '');
  const [end, setEnd] = useState(project?.end_date ?? '');
  const [status, setStatus] = useState(project?.status ?? 'ongoing');
  // Chủ nhiệm ngoài hệ thống: Excel có đề tài do người ngoài Viện chủ trì.
  const [leadMode, setLeadMode] = useState<'internal' | 'external'>(
    project && !project.lead_user_id ? 'external' : 'internal',
  );
  const [leadExternal, setLeadExternal] = useState(project?.lead_external_name ?? '');
  const [academicYear, setAcademicYear] = useState(project?.academic_year ?? '');
  const [budgetAmount, setBudgetAmount] = useState(project?.budget_amount ?? '');
  const [isTransferred, setIsTransferred] = useState(project?.is_transferred ?? false);
  const [transferProduct, setTransferProduct] = useState(project?.transfer_product ?? '');
  const [evidenceUrl, setEvidenceUrl] = useState(project?.evidence_url ?? '');
  const [members, setMembers] = useState<ContributorRow[]>(
    project?.members?.length
      ? project.members.map((m) => ({
          mode: m.user_id ? 'internal' : 'external',
          user_id: m.user_id ?? '',
          external_name: m.external_name ?? '',
          role: m.role_in_project ?? 'member',
        }))
      : [emptyContributor()],
  );
  const [submitting, setSubmitting] = useState(false);

  const { data: levels } = useAsync(() => researchApi.listProjectLevels(), []);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tên đề tài');
    if (!level) return toast.error('Chọn cấp đề tài');
    if (leadMode === 'internal' && !leadUserId) return toast.error('Chọn chủ nhiệm');
    if (leadMode === 'external' && !leadExternal.trim()) return toast.error('Nhập tên chủ nhiệm ngoài hệ thống');
    if (budgetAmount.trim() && !/^\d+(\.\d{1,2})?$/.test(budgetAmount.trim())) {
      return toast.error('Kinh phí phải là số, tối đa 2 chữ số thập phân (vd 803952000)');
    }
    const memberErr = validateContributors(members);
    if (memberErr) return toast.error(memberErr);

    const shared = {
      title: title.trim(),
      code: code || null,
      level,
      // XOR: gửi đúng một trong hai vế, vế còn lại null.
      lead_user_id: leadMode === 'internal' ? leadUserId : null,
      lead_external_name: leadMode === 'external' ? leadExternal.trim() : null,
      department_id: departmentId || null,
      start_date: start || null,
      end_date: end || null,
      academic_year: academicYear.trim() || null,
      budget_amount: budgetAmount.trim() || null,
      is_transferred: isTransferred,
      transfer_product: isTransferred ? transferProduct.trim() || null : null,
      evidence_url: evidenceUrl.trim() || null,
      status,
    };

    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateProject(project!.id, shared);
        // Cập nhật thành viên qua endpoint riêng (full replace)
        await researchApi.replaceProjectMembers(project!.id, toMembers(members));
      } else {
        await researchApi.createProject({ ...shared, members: toMembers(members) });
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
      title={editing ? 'Cập nhật đề tài' : 'Thêm đề tài NCKH'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            {editing ? 'Lưu' : 'Tạo'}
          </Button>
        </>
      }
    >
      <FormBody>
        <FormSection title="Định danh">
        <Field label="Tên đề tài" required className="md:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Mã đề tài">
          <Input value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Field label="Cấp đề tài" required>
          <Select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="">— Chọn —</option>
            {(levels ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </Select>
        </Field>
        </FormSection>

        <FormSection title="Chủ trì & thành viên">
        <Field label="Chủ nhiệm" required>
          <Select value={leadMode} onChange={(e) => setLeadMode(e.target.value as 'internal' | 'external')}>
            <option value="internal">Trong hệ thống</option>
            <option value="external">Ngoài hệ thống</option>
          </Select>
        </Field>
        {leadMode === 'internal' ? (
          <Field label="Chọn chủ nhiệm" required>
            <Select value={leadUserId} onChange={(e) => setLeadUserId(e.target.value)}>
              <option value="">— Chọn —</option>
              {(users?.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Họ tên chủ nhiệm" required>
            <Input value={leadExternal} onChange={(e) => setLeadExternal(e.target.value)} />
          </Field>
        )}
        <Field label="Phòng ban">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">— Suy từ chủ nhiệm —</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>
        </FormSection>

        <FormSection title="Thời gian & kinh phí">
        <Field label="Bắt đầu">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="Kết thúc">
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
        <Field label="Trạng thái">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(PROJECT_STATUS).map(([val, s]) => (
              <option key={val} value={val}>{s.label}</option>
            ))}
          </Select>
        </Field>
        <Field label="Năm học">
          <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" />
        </Field>
        <Field label="Kinh phí (VND)" hint="Excel ghi &quot;120 triệu&quot; — nhập số: 120000000">
          <Input
            value={budgetAmount}
            onChange={(e) => setBudgetAmount(e.target.value)}
            inputMode="decimal"
            placeholder="120000000"
          />
        </Field>

        </FormSection>

        <FormSection title="Chuyển giao & minh chứng">
        <div className="md:col-span-2 flex flex-col gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="h-4 w-4 accent-blueberry"
              checked={isTransferred}
              onChange={(e) => setIsTransferred(e.target.checked)}
            />
            Có chuyển giao sản phẩm
          </label>
          {isTransferred && (
            <Field label="Tên sản phẩm chuyển giao">
              <Input value={transferProduct} onChange={(e) => setTransferProduct(e.target.value)} />
            </Field>
          )}
        </div>

        <Field label="Link minh chứng" className="md:col-span-2">
          <Input value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} placeholder="https://" />
        </Field>

        </FormSection>

        <FormSection title="Thành viên" cols={1} hint="Chủ nhiệm phải nằm trong danh sách. Người ngoài Viện nhập tên trực tiếp.">
          <ContributorEditor rows={members} onChange={setMembers} users={users?.data ?? []} variant="member" />
        </FormSection>
      </FormBody>
    </Modal>
  );
}
