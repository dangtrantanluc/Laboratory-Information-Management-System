import { useState } from 'react';
import { BookText, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DescList, DescItem } from '@/components/ui/DescList';
import { Field, Input, Select } from '@/components/ui/Field';
import { Badge } from '@/components/ui/Badge';
import { PublicationTypeBadge } from '@/components/ui/StatusBadge';
import {
  ContributorEditor,
  emptyContributor,
  toAuthors,
  validateContributors,
  type ContributorRow,
} from '@/components/hr/ContributorEditor';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { canManageResearch } from '@/lib/rbac';
import type { Publication, PublicationType } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function Publications() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Publication | null>(null);
  const [viewTarget, setViewTarget] = useState<Publication | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Publication | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => researchApi.listPublications({ q: q || undefined, type: type || undefined, limit: 100 }),
    [q, type],
  );
  const { data: indexes } = useAsync(() => researchApi.listPubIndexes(), []);
  const canManage = canManageResearch(user);
  const indexLabel = (code: string | null) =>
    code ? (indexes ?? []).find((i) => i.code === code)?.label ?? code : '—';

  async function doDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await researchApi.deletePublication(deleteTarget.id);
      toast.success('Đã xóa');
      setDeleteTarget(null);
      reload();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setDeleting(false);
    }
  }

  const columns: Column<Publication>[] = [
    {
      key: 'title',
      header: 'Tiêu đề',
      sortValue: (p) => p.title,
      render: (p) => (
        <div>
          <p className="font-semibold text-ink">{p.title}</p>
          <p className="text-xs text-subink">
            {p.authors
              .slice()
              .sort((a, b) => a.author_order - b.author_order)
              .map((a) => a.name ?? a.external_name)
              .filter(Boolean)
              .join(', ')}
          </p>
        </div>
      ),
    },
    { key: 'type', header: 'Loại', render: (p) => <PublicationTypeBadge type={p.type} /> },
    {
      key: 'meta',
      header: 'Tạp chí / Số bằng',
      render: (p) => (p.type === 'paper' ? p.journal ?? '—' : p.patent_no ?? '—'),
    },
    { key: 'year', header: 'Năm', align: 'center', sortValue: (p) => p.year, render: (p) => p.year },
    {
      key: 'index',
      header: 'Chỉ số',
      render: (p) => (p.type === 'paper' ? indexLabel(p.category ?? p.index_code) : p.issuing_authority ?? '—'),
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            header: '',
            align: 'right' as const,
            render: (p: Publication) => (
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
        title="Bài báo & Sáng chế"
        description="Công bố khoa học, sáng chế / giải pháp hữu ích và đồng tác giả"
        icon={<BookText size={20} />}
        actions={
          canManage && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm công bố
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Tiêu đề…" className="max-w-xs flex-1" />
          <Select value={type} onChange={(e) => setType(e.target.value)} className="max-w-[180px]">
            <option value="">Mọi loại</option>
            <option value="paper">Bài báo</option>
            <option value="patent">Sáng chế / GPHI</option>
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
        <PublicationModal
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            reload();
            toast.success('Đã tạo công bố');
          }}
        />
      )}
      {editTarget && (
        <PublicationModal
          publication={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
            toast.success('Đã cập nhật');
          }}
        />
      )}
      {viewTarget && (
        <PublicationDetailModal
          publication={viewTarget}
          indexLabel={indexLabel}
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
        title="Xóa công bố"
        message={`Xóa "${deleteTarget?.title}"?`}
        confirmText="Xóa"
        loading={deleting}
      />
    </div>
  );
}

function PublicationDetailModal({
  publication: p,
  indexLabel,
  canManage,
  onClose,
  onEdit,
}: {
  publication: Publication;
  indexLabel: (code: string | null) => string;
  canManage: boolean;
  onClose: () => void;
  onEdit: () => void;
}) {
  const isPaper = p.type === 'paper';
  const authors = p.authors.slice().sort((a, b) => a.author_order - b.author_order);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={p.title}
      description={<PublicationTypeBadge type={p.type} />}
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
      <DescList>
        <DescItem label="Năm" value={p.year} />
        <DescItem label="Phòng ban" value={p.department_name} />
        {isPaper ? (
          <>
            <DescItem label="Tạp chí / Hội nghị" value={p.journal} full />
            <DescItem label="Chỉ số" value={<Badge tone="info">{indexLabel(p.category ?? p.index_code)}</Badge>} />
            <DescItem
              label="DOI"
              value={
                p.doi ? (
                  <a
                    href={`https://doi.org/${p.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-berry hover:underline"
                  >
                    {p.doi}
                  </a>
                ) : null
              }
            />
          </>
        ) : (
          <>
            <DescItem label="Số bằng" value={p.patent_no} />
            <DescItem label="Cơ quan cấp" value={p.issuing_authority} />
          </>
        )}
        <DescItem
          full
          label={`Tác giả (${authors.length})`}
          value={
            authors.length === 0 ? null : (
              <ol className="mt-1 divide-y divide-hairline overflow-hidden rounded-lg border border-hairline">
                {authors.map((a, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="text-sm text-ink">
                      <span className="mr-2 text-xs text-subink">{a.author_order}.</span>
                      {a.name ?? a.external_name ?? '—'}
                      {!a.user_id && <span className="ml-1.5 text-xs text-subink">(ngoài hệ thống)</span>}
                    </span>
                    {a.is_corresponding && <Badge tone="success">Tác giả liên hệ</Badge>}
                  </li>
                ))}
              </ol>
            )
          }
        />
      </DescList>
    </Modal>
  );
}

function PublicationModal({
  publication,
  onClose,
  onSaved,
}: {
  publication?: Publication;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const editing = !!publication;
  const [type, setType] = useState<PublicationType>(publication?.type ?? 'paper');
  const [title, setTitle] = useState(publication?.title ?? '');
  const [journal, setJournal] = useState(publication?.journal ?? '');
  const [year, setYear] = useState(String(publication?.year ?? new Date().getFullYear()));
  const [doi, setDoi] = useState(publication?.doi ?? '');
  const [indexCode, setIndexCode] = useState(publication?.index_code ?? '');
  const [patentNo, setPatentNo] = useState(publication?.patent_no ?? '');
  const [issuingAuthority, setIssuingAuthority] = useState(publication?.issuing_authority ?? '');
  const [departmentId, setDepartmentId] = useState(publication?.department_id ?? '');
  const [authors, setAuthors] = useState<ContributorRow[]>(
    publication?.authors?.length
      ? publication.authors
          .slice()
          .sort((a, b) => a.author_order - b.author_order)
          .map((a) => ({
            mode: a.user_id ? 'internal' : 'external',
            user_id: a.user_id ?? '',
            external_name: a.external_name ?? '',
            author_order: a.author_order,
            is_corresponding: a.is_corresponding,
          }))
      : [{ ...emptyContributor(1) }],
  );
  const [submitting, setSubmitting] = useState(false);

  const { data: indexes } = useAsync(() => researchApi.listPubIndexes(), []);
  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề');
    if (type === 'paper' && !journal.trim()) return toast.error('Bài báo cần tên tạp chí/hội nghị');
    if (type === 'paper' && !indexCode) return toast.error('Bài báo cần chọn chỉ số');
    if (type === 'patent' && !patentNo.trim()) return toast.error('Sáng chế cần số bằng');
    const y = Number(year);
    if (!Number.isInteger(y)) return toast.error('Năm không hợp lệ');
    const authorErr = validateContributors(authors);
    if (authorErr) return toast.error(authorErr);
    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updatePublication(publication!.id, {
          title: title.trim(),
          journal: type === 'paper' ? journal || null : null,
          year: y,
          doi: doi || null,
          index_code: type === 'paper' ? indexCode || null : null,
          patent_no: type === 'patent' ? patentNo || null : null,
          issuing_authority: type === 'patent' ? issuingAuthority || null : null,
          department_id: departmentId || null,
        });
        await researchApi.replacePublicationAuthors(publication!.id, toAuthors(authors));
      } else {
        await researchApi.createPublication({
          type,
          title: title.trim(),
          journal: type === 'paper' ? journal || null : null,
          year: y,
          doi: doi || null,
          index_code: type === 'paper' ? indexCode || null : null,
          patent_no: type === 'patent' ? patentNo || null : null,
          issuing_authority: type === 'patent' ? issuingAuthority || null : null,
          department_id: departmentId || null,
          authors: toAuthors(authors),
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
      title={editing ? 'Cập nhật công bố' : 'Thêm bài báo / sáng chế'}
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
        <Field label="Loại" required>
          <Select value={type} onChange={(e) => setType(e.target.value as PublicationType)} disabled={editing}>
            <option value="paper">Bài báo</option>
            <option value="patent">Sáng chế / GPHI</option>
          </Select>
        </Field>
        <Field label="Năm" required>
          <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
        <Field label="Tiêu đề" required className="sm:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>

        {type === 'paper' ? (
          <>
            <Field label="Tạp chí / Hội nghị" required>
              <Input value={journal} onChange={(e) => setJournal(e.target.value)} />
            </Field>
            <Field label="Chỉ số" required>
              <Select value={indexCode} onChange={(e) => setIndexCode(e.target.value)}>
                <option value="">— Chọn —</option>
                {(indexes ?? []).map((i) => (
                  <option key={i.code} value={i.code}>
                    {i.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="DOI" className="sm:col-span-2">
              <Input value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.1000/abc123" />
            </Field>
          </>
        ) : (
          <>
            <Field label="Số bằng" required>
              <Input value={patentNo} onChange={(e) => setPatentNo(e.target.value)} />
            </Field>
            <Field label="Cơ quan cấp">
              <Input value={issuingAuthority} onChange={(e) => setIssuingAuthority(e.target.value)} />
            </Field>
          </>
        )}

        <Field label="Phòng ban" className="sm:col-span-2">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">— Không gắn phòng —</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>

        <div className="sm:col-span-2">
          <p className="mb-2 text-sm font-medium text-ink">
            Tác giả <span className="text-overdue">*</span>
          </p>
          <ContributorEditor rows={authors} onChange={setAuthors} users={users?.data ?? []} variant="author" />
        </div>
      </div>
    </Modal>
  );
}
