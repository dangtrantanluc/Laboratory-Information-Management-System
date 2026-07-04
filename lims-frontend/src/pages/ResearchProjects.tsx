import { useState } from 'react';
import { FolderKanban, Plus, Pencil, Trash2, Users2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field, Input, Select } from '@/components/ui/Field';
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
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canManageResearch } from '@/lib/rbac';
import type { ResearchProject } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function ResearchProjects() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [level, setLevel] = useState('');
  const [editTarget, setEditTarget] = useState<ResearchProject | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ResearchProject | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => researchApi.listProjects({ q: q || undefined, level: level || undefined, limit: 100 }),
    [q, level],
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
    { key: 'level', header: 'Cấp', render: (p) => <Badge tone="info">{levelLabel(p.level)}</Badge> },
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
    { key: 'status', header: 'Trạng thái', render: (p) => p.status },
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
              <div className="flex justify-end gap-1">
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
          <SearchInput value={q} onChange={setQ} placeholder="Tên đề tài…" className="max-w-xs flex-1" />
          <Select value={level} onChange={(e) => setLevel(e.target.value)} className="max-w-[200px]">
            <option value="">Mọi cấp</option>
            {(levels ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable columns={columns} rows={data?.data ?? []} rowKey={(p) => p.id} loading={loading} pageSize={12} />
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
  const [status, setStatus] = useState(project?.status ?? 'in_progress');
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
    if (!leadUserId) return toast.error('Chọn chủ nhiệm');
    const memberErr = validateContributors(members);
    if (memberErr) return toast.error(memberErr);
    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updateProject(project!.id, {
          title: title.trim(),
          code: code || null,
          level,
          lead_user_id: leadUserId,
          department_id: departmentId || null,
          start_date: start || null,
          end_date: end || null,
          status,
        });
        // Cập nhật thành viên qua endpoint riêng (full replace)
        await researchApi.replaceProjectMembers(project!.id, toMembers(members));
      } else {
        await researchApi.createProject({
          title: title.trim(),
          code: code || null,
          level,
          lead_user_id: leadUserId,
          department_id: departmentId || null,
          start_date: start || null,
          end_date: end || null,
          status,
          members: toMembers(members),
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
      title={editing ? 'Cập nhật đề tài' : 'Thêm đề tài NCKH'}
      description="Chủ nhiệm phải nằm trong danh sách thành viên."
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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tên đề tài" required className="sm:col-span-2">
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
        <Field label="Chủ nhiệm" required>
          <Select value={leadUserId} onChange={(e) => setLeadUserId(e.target.value)}>
            <option value="">— Chọn —</option>
            {(users?.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </Field>
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
        <Field label="Bắt đầu">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="Kết thúc">
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
        <Field label="Trạng thái">
          <Input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="in_progress" />
        </Field>
        <div className="sm:col-span-2">
          <p className="mb-2 text-sm font-medium text-ink">
            Thành viên <span className="text-overdue">*</span>
          </p>
          <ContributorEditor rows={members} onChange={setMembers} users={users?.data ?? []} variant="member" />
        </div>
      </div>
    </Modal>
  );
}
