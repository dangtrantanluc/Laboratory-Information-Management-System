import { useState } from 'react';
import { BookText, Plus, Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  DescList,
  DescItem,
  DescLink,
  DescPeople,
  DescSection,
  DetailHero,
} from '@/components/ui/DescList';
import { Field, Input, Select } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
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
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { canManageResearch } from '@/lib/rbac';
import { formatDate } from '@/lib/format';
import { PATENT_KIND_LABELS } from '@/types';
import type { PatentKind, Publication, PublicationType } from '@/types';
import * as researchApi from '@/api/research';
import * as usersApi from '@/api/users';

export function Publications() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [type, setType] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Publication | null>(null);
  const [viewTarget, setViewTarget] = useState<Publication | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Publication | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, reload } = useAsync(
    () => researchApi.listPublications({ q: dq || undefined, type: type || undefined, limit: 100 }),
    [dq, type],
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
    { key: 'type', priority: 1, header: 'Loại', render: (p) => <PublicationTypeBadge type={p.type} /> },
    {
      key: 'meta',
      header: 'Tạp chí / Số bằng',
      render: (p) => (p.type === 'paper' ? p.journal ?? '—' : p.patent_no ?? '—'),
    },
    { key: 'year', priority: 1, header: 'Năm', align: 'center', sortValue: (p) => p.year, render: (p) => p.year },
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
          <SearchInput value={q} onChange={setQ} placeholder="Tiêu đề…" className="w-full sm:max-w-xs sm:flex-1" />
          <Select value={type} onChange={(e) => setType(e.target.value)} className="w-full sm:max-w-[180px]">
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
  const isPatent = p.type === 'patent';
  const authors = p.authors.slice().sort((a, b) => a.author_order - b.author_order);

  const indexBadges = [
    p.is_scie && { label: 'SCIE', tone: 'success' as const },
    p.is_ssci && { label: 'SSCI', tone: 'success' as const },
    p.is_scopus && { label: 'Scopus', tone: 'info' as const },
    p.is_aci && { label: 'ACI', tone: 'neutral' as const },
  ].filter(Boolean) as Array<{ label: string; tone: 'success' | 'info' | 'neutral' }>;

  const people = authors.map((a) => ({
    // Thứ tự tác giả là thông tin nghiệp vụ (tác giả chính đứng đầu) nên giữ số.
    name: `${a.author_order}. ${a.name ?? a.external_name ?? 'Không rõ'}`,
    role: a.is_corresponding ? 'Tác giả liên hệ' : null,
    external: !a.user_id,
  }));

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={p.title}
      description={isPatent ? 'Văn bằng sở hữu trí tuệ' : 'Công bố khoa học'}
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
              {/* Có patent_kind thì nó ĐÃ nói rõ hơn ("Sáng chế") so với nhãn loại
                  ("Sáng chế / GPHI") — hiện cả hai là hai chip trùng nghĩa cạnh nhau. */}
              {isPatent && p.patent_kind ? (
                <Badge tone="info">{PATENT_KIND_LABELS[p.patent_kind]}</Badge>
              ) : (
                <PublicationTypeBadge type={p.type} />
              )}
              {!isPatent && p.pub_scope && (
                <Badge tone="info">{p.pub_scope === 'international' ? 'Quốc tế' : 'Trong nước'}</Badge>
              )}
              {isPaper && <Badge tone="neutral">{indexLabel(p.category ?? p.index_code)}</Badge>}
              {indexBadges.map((b) => (
                <Badge key={b.label} tone={b.tone}>
                  {b.label}
                </Badge>
              ))}
            </>
          }
          metricLabel="Năm công bố"
          metric={p.year}
        />

        {!isPatent && (
          <DescSection title="Nơi công bố">
            <DescList>
              <DescItem
                full
                label={p.type === 'conference' ? 'Tên kỷ yếu / hội nghị' : 'Tên tạp chí'}
                value={p.journal}
              />
              <DescItem
                label="DOI"
                value={
                  p.doi ? (
                    <a
                      href={`https://doi.org/${p.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blueberry hover:underline"
                    >
                      {p.doi}
                    </a>
                  ) : null
                }
              />
              <DescItem label="Năm học" value={p.academic_year} />
            </DescList>
          </DescSection>
        )}

        {isPatent && (
          <DescSection title="Văn bằng">
            <DescList>
              <DescItem label="Số bằng" value={p.patent_no} emphasis />
              <DescItem label="Chủ bằng" value={p.patent_holder} />
              <DescItem full label="Cơ quan cấp văn bằng" value={p.issuing_authority} />
              <DescItem label="Số đơn" value={p.application_no} />
              <DescItem
                label="Ngày nộp đơn"
                value={p.application_date ? formatDate(p.application_date) : null}
              />
              <DescItem
                label="Ngày cấp văn bằng"
                value={p.granted_date ? formatDate(p.granted_date) : null}
              />
              <DescItem label="Năm học" value={p.academic_year} />
            </DescList>
          </DescSection>
        )}

        <DescSection title="Tác giả & minh chứng">
          <DescList>
            <DescPeople label="Tác giả" people={people} />
            <DescItem label="Phòng ban" value={p.department_name} />
            <DescLink url={p.evidence_url} full={false} />
          </DescList>
        </DescSection>
      </div>
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
  // Bảng sáng chế của Excel chia ba mục I/II/III bằng dòng tiêu đề, không phải cột.
  const [patentKind, setPatentKind] = useState<string>(publication?.patent_kind ?? '');
  const [applicationNo, setApplicationNo] = useState(publication?.application_no ?? '');
  const [applicationDate, setApplicationDate] = useState(publication?.application_date ?? '');
  const [grantedDate, setGrantedDate] = useState(publication?.granted_date ?? '');
  const [patentHolder, setPatentHolder] = useState(publication?.patent_holder ?? '');
  // Hai bảng công bố (trong nước / quốc tế) phân biệt bằng pub_scope; bốn cờ chỉ mục
  // là bốn cột riêng của bảng quốc tế.
  const [pubScope, setPubScope] = useState<string>(publication?.pub_scope ?? '');
  const [isScie, setIsScie] = useState(publication?.is_scie ?? false);
  const [isSsci, setIsSsci] = useState(publication?.is_ssci ?? false);
  const [isScopus, setIsScopus] = useState(publication?.is_scopus ?? false);
  const [isAci, setIsAci] = useState(publication?.is_aci ?? false);
  const [academicYear, setAcademicYear] = useState(publication?.academic_year ?? '');
  const [evidenceUrl, setEvidenceUrl] = useState(publication?.evidence_url ?? '');
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

  const isPatent = type === 'patent';
  // Bài báo VÀ báo cáo hội nghị đều cần tên nơi đăng (tạp chí / kỷ yếu) — trước đây
  // nhánh conference bị ép journal = null nên mất trắng cột "Tên kỷ yếu/hội nghị".
  const needsVenue = type === 'paper' || type === 'conference';

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề');
    if (needsVenue && !journal.trim()) {
      return toast.error(type === 'paper' ? 'Bài báo cần tên tạp chí' : 'Báo cáo cần tên kỷ yếu/hội nghị');
    }
    if (type === 'paper' && !indexCode) return toast.error('Bài báo cần chọn chỉ số');
    if (isPatent && !patentNo.trim()) return toast.error('Sáng chế cần số bằng');
    if (isPatent && !issuingAuthority.trim()) return toast.error('Sáng chế cần cơ quan cấp văn bằng');
    const y = Number(year);
    if (!Number.isInteger(y)) return toast.error('Năm không hợp lệ');
    const authorErr = validateContributors(authors);
    if (authorErr) return toast.error(authorErr);

    const shared = {
      title: title.trim(),
      journal: needsVenue ? journal.trim() || null : null,
      year: y,
      doi: doi.trim() || null,
      index_code: type === 'paper' ? indexCode || null : null,
      pub_scope: isPatent ? null : (pubScope || null),
      is_scie: isPatent ? false : isScie,
      is_ssci: isPatent ? false : isSsci,
      is_scopus: isPatent ? false : isScopus,
      is_aci: isPatent ? false : isAci,
      academic_year: academicYear.trim() || null,
      patent_no: isPatent ? patentNo.trim() || null : null,
      issuing_authority: isPatent ? issuingAuthority.trim() || null : null,
      application_no: isPatent ? applicationNo.trim() || null : null,
      application_date: isPatent ? applicationDate || null : null,
      granted_date: isPatent ? grantedDate || null : null,
      patent_holder: isPatent ? patentHolder.trim() || null : null,
      patent_kind: isPatent ? ((patentKind || null) as PatentKind | null) : null,
      evidence_url: evidenceUrl.trim() || null,
      department_id: departmentId || null,
    };

    setSubmitting(true);
    try {
      if (editing) {
        await researchApi.updatePublication(publication!.id, shared);
        await researchApi.replacePublicationAuthors(publication!.id, toAuthors(authors));
      } else {
        await researchApi.createPublication({ ...shared, type, authors: toAuthors(authors) });
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
      size="xl"
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
      <FormBody>
        <FormSection title="Định danh">
        <Field label="Loại" required>
          <Select value={type} onChange={(e) => setType(e.target.value as PublicationType)} disabled={editing}>
            <option value="paper">Bài báo</option>
            <option value="conference">Báo cáo hội nghị / kỷ yếu</option>
            <option value="patent">Sáng chế / GPHI / Giống cây trồng</option>
          </Select>
        </Field>
        <Field label="Năm" required>
          <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
        <Field label="Tiêu đề" required className="md:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        </FormSection>

        <FormSection title={needsVenue ? 'Nơi công bố' : 'Văn bằng'}>
        {needsVenue ? (
          <>
            <Field label={type === 'paper' ? 'Tên tạp chí' : 'Tên kỷ yếu / hội nghị'} required>
              <Input value={journal} onChange={(e) => setJournal(e.target.value)} />
            </Field>
            {type === 'paper' ? (
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
            ) : (
              <Field label="Phạm vi">
                <Select value={pubScope} onChange={(e) => setPubScope(e.target.value)}>
                  <option value="">— Chưa phân loại —</option>
                  <option value="domestic">Trong nước</option>
                  <option value="international">Quốc tế</option>
                </Select>
              </Field>
            )}

            {type === 'paper' && (
              <Field label="Phạm vi" hint="Excel tách hai bảng: trong nước và quốc tế">
                <Select value={pubScope} onChange={(e) => setPubScope(e.target.value)}>
                  <option value="">— Chưa phân loại —</option>
                  <option value="domestic">Trong nước</option>
                  <option value="international">Quốc tế</option>
                </Select>
              </Field>
            )}
            <Field label="DOI" className={type === 'paper' ? undefined : 'md:col-span-2'}>
              <Input value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.1000/abc123" />
            </Field>

            <div className="md:col-span-2">
              <p className="mb-2 text-sm font-medium text-ink">Chỉ mục quốc tế</p>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {(
                  [
                    ['SCIE', isScie, setIsScie],
                    ['SSCI', isSsci, setIsSsci],
                    ['Scopus', isScopus, setIsScopus],
                    ['ACI', isAci, setIsAci],
                  ] as Array<[string, boolean, (v: boolean) => void]>
                ).map(([label, checked, set]) => (
                  <label key={label} className="flex cursor-pointer items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-blueberry"
                      checked={checked}
                      onChange={(e) => set(e.target.checked)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <Field label="Loại văn bằng" required>
              <Select value={patentKind} onChange={(e) => setPatentKind(e.target.value)}>
                <option value="">— Chọn —</option>
                {Object.entries(PATENT_KIND_LABELS).map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </Select>
            </Field>
            <Field label="Số bằng" required>
              <Input value={patentNo} onChange={(e) => setPatentNo(e.target.value)} />
            </Field>
            <Field label="Cơ quan cấp văn bằng" required>
              <Input value={issuingAuthority} onChange={(e) => setIssuingAuthority(e.target.value)} />
            </Field>
            <Field label="Chủ bằng">
              <Input value={patentHolder} onChange={(e) => setPatentHolder(e.target.value)} />
            </Field>
            <Field label="Số đơn">
              <Input value={applicationNo} onChange={(e) => setApplicationNo(e.target.value)} />
            </Field>
            <Field label="Ngày nộp đơn">
              <Input type="date" value={applicationDate ?? ''} onChange={(e) => setApplicationDate(e.target.value)} />
            </Field>
            <Field label="Ngày cấp văn bằng">
              <Input type="date" value={grantedDate ?? ''} onChange={(e) => setGrantedDate(e.target.value)} />
            </Field>
          </>
        )}
        </FormSection>

        <FormSection title="Hồ sơ & minh chứng">
        <Field label="Năm học">
          <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} placeholder="2024-2025" />
        </Field>
        <Field label="Link minh chứng">
          <Input value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} placeholder="https://" />
        </Field>

        <Field label="Phòng ban" className="md:col-span-2">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">— Không gắn phòng —</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>
        </FormSection>

        <FormSection title="Tác giả" cols={1} hint="Tác giả nội bộ chọn từ danh sách; người ngoài Viện nhập tên trực tiếp.">
          <ContributorEditor rows={authors} onChange={setAuthors} users={users?.data ?? []} variant="author" />
        </FormSection>
      </FormBody>
    </Modal>
  );
}
