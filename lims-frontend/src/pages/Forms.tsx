import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FileText, Plus, Download, Upload, ChevronRight, ChevronDown, FolderClosed, FileSpreadsheet, FileUp, History } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { FormBody, FormSection } from '@/components/ui/FormSection';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/States';
import { formatDateTime } from '@/lib/format';
import { RegistrationStatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { useDebounced } from '@/lib/useDebounced';
import { describeError } from '@/lib/errors';
import { cn } from '@/lib/cn';
import { canManageForms, canSubmitForms } from '@/lib/rbac';
import { FormFileManager } from '@/components/forms/FormFileManager';
import { FORM_CATEGORY_LABELS, type FormSubmission, type FormTemplate } from '@/types';
import * as formsApi from '@/api/forms';

/** Cây điều khoản ISO/IEC 17025 (theo cấu trúc thư mục kho VILAS). */
const CLAUSE_TREE: { code: string; title: string; children: { code: string; title: string }[] }[] = [
  { code: '2', title: 'Mục tiêu chất lượng', children: [] },
  { code: '3', title: 'Quyền hạn và Trách nhiệm', children: [] },
  {
    code: '4', title: 'Yêu cầu chung',
    children: [
      { code: '4.1', title: 'Tính khách quan' },
      { code: '4.2', title: 'Cam kết bảo mật' },
    ],
  },
  { code: '5', title: 'Yêu cầu về cơ cấu', children: [] },
  {
    code: '6', title: 'Yêu cầu về nguồn lực',
    children: [
      { code: '6.2', title: 'Nhân sự' },
      { code: '6.3', title: 'Cơ sở vật chất và điều kiện môi trường' },
      { code: '6.4', title: 'Thiết bị' },
      { code: '6.5', title: 'Liên kết chuẩn đo lường' },
      { code: '6.6', title: 'Sản phẩm và dịch vụ do bên ngoài cung cấp' },
    ],
  },
  {
    code: '7', title: 'Yêu cầu về quá trình',
    children: [
      { code: '7.1', title: 'Xem xét yêu cầu, đề nghị thầu và hợp đồng' },
      { code: '7.2', title: 'Giá trị sử dụng của phương pháp' },
      { code: '7.3', title: 'Lấy mẫu' },
      { code: '7.4', title: 'Xử lý mẫu' },
      { code: '7.5', title: 'Hồ sơ kỹ thuật' },
      { code: '7.6', title: 'Đánh giá độ không đảm bảo đo' },
      { code: '7.7', title: 'Đảm bảo giá trị sử dụng của kết quả' },
      { code: '7.8', title: 'Báo cáo kết quả' },
      { code: '7.9', title: 'Giải quyết phàn nàn' },
      { code: '7.10', title: 'Công việc không phù hợp' },
      { code: '7.11', title: 'Kiểm soát dữ liệu - quản lý thông tin' },
    ],
  },
  {
    code: '8', title: 'Yêu cầu về hệ thống quản lý',
    children: [
      { code: '8.2', title: 'Tài liệu hệ thống quản lý' },
      { code: '8.3', title: 'Kiểm soát tài liệu' },
      { code: '8.4', title: 'Kiểm soát hồ sơ' },
      { code: '8.5', title: 'Hành động giải quyết rủi ro và cơ hội' },
      { code: '8.6', title: 'Cải tiến' },
      { code: '8.7', title: 'Hành động khắc phục' },
      { code: '8.8', title: 'Đánh giá nội bộ' },
      { code: '8.9', title: 'Xem xét của lãnh đạo' },
    ],
  },
];

/** template khớp điều khoản đã chọn: code có '.' → khớp chính xác; code gốc → gồm mọi tiểu mục. */
function matchClause(clause: string, selected: string | null): boolean {
  if (!selected) return true;
  if (selected.includes('.')) return clause === selected;
  return clause === selected || clause.startsWith(selected + '.');
}

type Tab = 'templates' | 'submissions' | 'history';

export function Forms() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const initialTab = (params.get('tab') as Tab) ?? 'templates';
  const [tab, setTab] = useState<Tab>(
    ['templates', 'submissions', 'history'].includes(initialTab) ? initialTab : 'templates',
  );
  const canManage = canManageForms(user);
  const canSubmit = canSubmitForms(user);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Kho biểu mẫu VILAS"
        description="Biểu mẫu ISO/IEC 17025 dùng chung — tải về, điền, nộp minh chứng"
        icon={<FileText size={20} />}
      />
      <div className="flex gap-2">
        <Button variant={tab === 'templates' ? 'primary' : 'secondary'} onClick={() => setTab('templates')}>
          Kho biểu mẫu
        </Button>
        <Button variant={tab === 'submissions' ? 'primary' : 'secondary'} onClick={() => setTab('submissions')}>
          Minh chứng đã nộp
        </Button>
        <Button variant={tab === 'history' ? 'primary' : 'secondary'} onClick={() => setTab('history')}>
          <History size={15} /> Lịch sử tệp
        </Button>
      </div>
      {tab === 'templates' ? (
        <TemplatesTab canManage={canManage} canSubmit={canSubmit} />
      ) : tab === 'submissions' ? (
        <SubmissionsTab />
      ) : (
        <HistoryTab />
      )}
    </div>
  );
}

// ===== Kho biểu mẫu (cây điều khoản + bảng) =====
function TemplatesTab({ canManage, canSubmit }: { canManage: boolean; canSubmit: boolean }) {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<FormTemplate | null>(null);
  const [submitFor, setSubmitFor] = useState<FormTemplate | null>(null);
  const [fileFor, setFileFor] = useState<FormTemplate | null>(null);

  const { data, loading, reload } = useAsync(
    () => formsApi.listAllTemplates({ active_only: true }),
    [],
  );
  const all = data ?? [];

  const countFor = (code: string) => all.filter((t) => matchClause(t.iso_clause, code)).length;

  // Bám theo bản mới nhất sau khi thay tệp để modal không giữ dữ liệu cũ.
  const fileTarget = fileFor ? all.find((t) => t.id === fileFor.id) ?? fileFor : null;

  const rows = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return all.filter((t) => {
      if (!matchClause(t.iso_clause, selected)) return false;
      if (!ql) return true;
      return t.code.toLowerCase().includes(ql) || t.title.toLowerCase().includes(ql);
    });
  }, [all, selected, q]);

  function toggle(code: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }
  function pickSection(code: string, hasChildren: boolean) {
    setSelected(code);
    if (hasChildren) setExpanded((prev) => new Set(prev).add(code));
  }

  const rowCls = (active: boolean) =>
    cn(
      'flex-1 truncate rounded px-2 py-1 text-left text-sm hover:bg-plate',
      active ? 'bg-blueberry/10 font-semibold text-blueberry' : 'text-ink',
    );

  const isRealCode = (t: FormTemplate) => /^(BM|QT|HD)\b/i.test(t.code) && t.code !== t.title;

  const columns: Column<FormTemplate>[] = [
    {
      key: 'title',
      header: 'Biểu mẫu',
      sortValue: (t) => t.title.toLowerCase(),
      render: (t) => (
        <div className="min-w-0 max-w-[460px]">
          <div className="truncate font-medium text-ink" title={t.title}>
            {t.title}
          </div>
          {isRealCode(t) && (
            <div className="truncate font-mono text-xs text-subink">{t.code}</div>
          )}
        </div>
      ),
    },
    {
      key: 'iso_clause',
      priority: 1,
      header: 'Điều khoản',
      sortValue: (t) => t.iso_clause,
      render: (t) => <Badge tone="neutral">{t.iso_clause}</Badge>,
    },
    {
      key: 'category',
      priority: 1,
      header: 'Loại',
      render: (t) => (
        <span className="whitespace-nowrap text-sm">{FORM_CATEGORY_LABELS[t.category] ?? t.category}</span>
      ),
    },
    {
      key: 'files',
      header: 'Tệp',
      render: (t) => {
        const current = t.files[0] ?? null;
        return (
          <div className="flex items-center gap-2">
            {current ? (
              <button
                title={current.file_name}
                className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-blueberry hover:underline"
                onClick={(e) => {
                  e.stopPropagation();
                  formsApi.openFormFile(current.id).catch((err) => toast.error(describeError(err).title));
                }}
              >
                <Download size={14} /> Tải
              </button>
            ) : (
              <span className="text-subink">—</span>
            )}
            <button
              title={canManage ? 'Tải lên / thay tệp · xem lịch sử' : 'Xem lịch sử tệp'}
              className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-stem hover:text-blueberry hover:underline"
              onClick={(e) => {
                e.stopPropagation();
                setFileFor(t);
              }}
            >
              {canManage ? <FileUp size={14} /> : <History size={14} />}
              {canManage ? (current ? 'Thay' : 'Tải lên') : 'Lịch sử'}
            </button>
          </div>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      render: (t) =>
        canSubmit ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setSubmitFor(t);
            }}
          >
            <Upload size={14} /> Nộp
          </Button>
        ) : null,
    },
  ];

  const selectedLabel = (() => {
    if (!selected) return 'Tất cả biểu mẫu';
    for (const s of CLAUSE_TREE) {
      if (s.code === selected) return `${s.code}. ${s.title}`;
      const c = s.children.find((ch) => ch.code === selected);
      if (c) return `${c.code} ${c.title}`;
    }
    return selected;
  })();

  return (
    <div className="flex flex-col items-start gap-4 lg:flex-row">
      {/* Cây điều khoản ISO */}
      <Card className="w-full shrink-0 p-2 lg:w-96">
        <button onClick={() => setSelected(null)} className={cn('mb-1 flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-plate', selected === null ? 'bg-blueberry/10 font-semibold text-blueberry' : 'text-ink')}>
          <FolderClosed size={15} /> Tất cả biểu mẫu
          <span className="ml-auto text-xs text-subink">{all.length}</span>
        </button>
        {CLAUSE_TREE.map((sec) => {
          const hasCh = sec.children.length > 0;
          const isOpen = expanded.has(sec.code);
          return (
            <div key={sec.code}>
              <div className="flex items-center">
                <button
                  onClick={() => (hasCh ? toggle(sec.code) : setSelected(sec.code))}
                  className="p-1 text-subink hover:text-ink"
                  aria-label="toggle"
                >
                  {hasCh ? (isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <span className="inline-block w-[14px]" />}
                </button>
                <button onClick={() => pickSection(sec.code, hasCh)} className={rowCls(selected === sec.code)}>
                  {sec.code}. {sec.title}
                  <span className="ml-1 text-xs text-subink">({countFor(sec.code)})</span>
                </button>
              </div>
              {isOpen &&
                sec.children.map((ch) => (
                  <div key={ch.code} className="flex items-center">
                    <span className="inline-block w-[22px]" />
                    <button onClick={() => setSelected(ch.code)} className={rowCls(selected === ch.code)}>
                      {ch.code} {ch.title}
                      <span className="ml-1 text-xs text-subink">({countFor(ch.code)})</span>
                    </button>
                  </div>
                ))}
            </div>
          );
        })}
      </Card>

      {/* Bảng biểu mẫu */}
      <Card className="w-full min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <div className="text-sm font-semibold text-ink">
            {selectedLabel} <span className="text-subink">· {rows.length} biểu mẫu</span>
          </div>
          <SearchInput value={q} onChange={setQ} placeholder="Mã / tên biểu mẫu…" className="max-w-xs" />
          {canManage && (
            <Button className="ml-auto" onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Thêm biểu mẫu
            </Button>
          )}
        </div>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(t) => t.id}
          loading={loading}
          pageSize={15}
          onRowClick={canManage ? (t) => setEditing(t) : undefined}
        />
      </Card>

      {(createOpen || editing) && (
        <TemplateModal
          template={editing}
          onClose={() => {
            setCreateOpen(false);
            setEditing(null);
          }}
          onDone={() => {
            setCreateOpen(false);
            setEditing(null);
            reload();
          }}
        />
      )}
      {submitFor && (
        <SubmissionModal
          template={submitFor}
          onClose={() => setSubmitFor(null)}
          onDone={() => {
            setSubmitFor(null);
            toast.success('Đã nộp minh chứng — Phòng QLCL sẽ nhận thông báo');
          }}
        />
      )}
      {fileTarget && (
        <FormFileManager
          owner="templates"
          ownerId={fileTarget.id}
          title={`Tệp biểu mẫu — ${fileTarget.code}`}
          subtitle={fileTarget.title}
          currentFile={fileTarget.files[0] ?? null}
          canEdit={canManage}
          allowDelete
          onClose={() => setFileFor(null)}
          onChanged={reload}
        />
      )}
    </div>
  );
}

function TemplateModal({
  template,
  onClose,
  onDone,
}: {
  template: FormTemplate | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [code, setCode] = useState(template?.code ?? '');
  const [title, setTitle] = useState(template?.title ?? '');
  const [clause, setClause] = useState(template?.iso_clause ?? '');
  const [category, setCategory] = useState(template?.category ?? 'BM');
  const [year, setYear] = useState<string>(template?.year ? String(template.year) : '');
  const [note, setNote] = useState(template?.note ?? '');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!code.trim() || !title.trim() || !clause.trim()) return toast.error('Nhập mã, tên và điều khoản');
    setSubmitting(true);
    try {
      const body = {
        code: code.trim(),
        title: title.trim(),
        iso_clause: clause.trim(),
        category,
        year: year ? Number(year) : null,
        note: note || null,
      };
      let tpl: FormTemplate;
      if (template) tpl = await formsApi.updateTemplate(template.id, body);
      else tpl = await formsApi.createTemplate(body);
      // Dùng endpoint riêng (/forms/templates/{id}/file) chứ KHÔNG phải /attachments
      // generic: chỉ đường này mới kiểm form:manage + phạm vi phòng ban.
      if (file) await formsApi.replaceFormFile('templates', tpl.id, file);
      onDone();
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
      title={template ? 'Sửa biểu mẫu' : 'Thêm biểu mẫu'}
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
      <FormBody>
        <FormSection title="Định danh">
          <Field label="Mã biểu mẫu" required>
            <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="vd BM 6.2.01" />
          </Field>
          <Field label="Tên biểu mẫu" required>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Điều khoản ISO" required>
            <Input value={clause} onChange={(e) => setClause(e.target.value)} placeholder="6.2" />
          </Field>
          <Field label="Loại">
            <Select value={category} onChange={(e) => setCategory(e.target.value as typeof category)}>
              <option value="BM">Biểu mẫu</option>
              <option value="QT">Quy trình</option>
              <option value="HD">Hướng dẫn</option>
              <option value="TL">Tài liệu</option>
            </Select>
          </Field>
          <Field label="Năm">
            <Input value={year} onChange={(e) => setYear(e.target.value)} placeholder="2026" />
          </Field>
        </FormSection>

        <FormSection title="Tệp & ghi chú" cols={1}>
          <Field label="Tệp mẫu (docx/pdf…)">
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Field>
          <Field label="Ghi chú">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </FormSection>
      </FormBody>
    </Modal>
  );
}

function SubmissionModal({
  template,
  onClose,
  onDone,
}: {
  template: FormTemplate;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [year, setYear] = useState<string>(String(new Date().getFullYear()));
  const [note, setNote] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!file) return toast.error('Chọn tệp minh chứng để nộp');
    setSubmitting(true);
    try {
      const sub = await formsApi.createSubmission({
        template_id: template.id,
        year: year ? Number(year) : null,
        note: note || null,
      });
      // Endpoint riêng: kiểm form:submit + phòng ban + khoá tệp sau khi duyệt.
      await formsApi.replaceFormFile('submissions', sub.id, file);
      onDone();
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
      title={`Nộp minh chứng — ${template.code}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Nộp
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-subink">{template.title}</p>
        <Field label="Năm">
          <Input value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
        <Field label="Tệp minh chứng" required>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
        <Field label="Ghi chú">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

// ===== Minh chứng đã nộp =====
function SubmissionsTab() {
  const toast = useToast();
  const { user } = useAuth();
  const { data, loading, reload } = useAsync(() => formsApi.listSubmissions({ limit: 200 }), []);
  const [deptId, setDeptId] = useState('');
  const [year, setYear] = useState('');
  const [exporting, setExporting] = useState(false);
  const [fileFor, setFileFor] = useState<FormSubmission | null>(null);
  const canSubmit = canSubmitForms(user);

  const all = data?.data ?? [];
  const deptOptions = Array.from(
    new Map(all.filter((s) => s.department_name).map((s) => [s.department_id, s.department_name as string])).entries(),
  );
  const yearOptions = Array.from(new Set(all.map((s) => s.year).filter(Boolean))).sort() as number[];

  const rows = all.filter(
    (s) => (!deptId || s.department_id === deptId) && (!year || String(s.year) === year),
  );
  // Bám bản mới nhất sau khi thay tệp (trạng thái có thể đổi rejected → pending).
  const fileTarget = fileFor ? all.find((s) => s.id === fileFor.id) ?? fileFor : null;

  async function exportXlsx() {
    setExporting(true);
    try {
      await formsApi.exportSubmissionsXlsx({
        department_id: deptId || undefined,
        year: year ? Number(year) : undefined,
      });
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const columns: Column<FormSubmission>[] = [
    { key: 'template', header: 'Mã BM', render: (s) => <span className="font-semibold text-ink">{s.template_code}</span> },
    { key: 'title', header: 'Tên biểu mẫu', render: (s) => <span className="text-ink">{s.template_title ?? '—'}</span> },
    { key: 'department', header: 'Phòng', render: (s) => s.department_name ?? '—' },
    { key: 'year', header: 'Năm', render: (s) => s.year ?? '—' },
    { key: 'by', header: 'Người nộp', render: (s) => s.submitted_by_name ?? '—' },
    { key: 'at', header: 'Thời gian nộp', render: (s) => new Date(s.submitted_at).toLocaleString('vi-VN') },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (s) => (
        <div className="flex flex-col gap-0.5">
          <RegistrationStatusBadge status={s.status} />
          {s.status === 'rejected' && s.reject_reason && (
            <span className="text-xs text-subink" title={s.reject_reason}>
              {s.reject_reason}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'files',
      header: 'Tệp',
      render: (s) => {
        const current = s.files[0] ?? null;
        // Đã duyệt thì khóa tệp (backend chặn) — chỉ còn xem lịch sử.
        const editable = canSubmit && s.status !== 'approved';
        return (
          <div className="flex items-center gap-2">
            {current ? (
              <button
                title={current.file_name}
                className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-blueberry hover:underline"
                onClick={() =>
                  formsApi.openFormFile(current.id).catch((e) => toast.error(describeError(e).title))
                }
              >
                <Download size={14} /> Tải
              </button>
            ) : (
              <span className="text-subink">—</span>
            )}
            <button
              title={editable ? 'Thay tệp · xem lịch sử' : 'Xem lịch sử tệp'}
              className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-stem hover:text-blueberry hover:underline"
              onClick={() => setFileFor(s)}
            >
              {editable ? <FileUp size={14} /> : <History size={14} />}
              {editable ? 'Thay' : 'Lịch sử'}
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
        <Select value={deptId} onChange={(e) => setDeptId(e.target.value)} className="w-full sm:max-w-[240px]">
          <option value="">Tất cả phòng</option>
          {deptOptions.map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </Select>
        <Select value={year} onChange={(e) => setYear(e.target.value)} className="w-full sm:max-w-[140px]">
          <option value="">Tất cả năm</option>
          {yearOptions.map((y) => (
            <option key={y} value={String(y)}>{y}</option>
          ))}
        </Select>
        <span className="text-sm text-subink">{rows.length} minh chứng</span>
        <Button variant="secondary" className="ml-auto" onClick={exportXlsx} loading={exporting} disabled={!rows.length}>
          <FileSpreadsheet size={16} /> In danh sách
        </Button>
      </div>
      <DataTable columns={columns} rows={rows} rowKey={(s) => s.id} loading={loading} pageSize={15} />
      {fileTarget && (
        <FormFileManager
          owner="submissions"
          ownerId={fileTarget.id}
          title={`Tệp minh chứng — ${fileTarget.template_code ?? ''}`}
          subtitle={`${fileTarget.template_title ?? ''}${fileTarget.department_name ? ` · ${fileTarget.department_name}` : ''}`}
          currentFile={fileTarget.files[0] ?? null}
          canEdit={canSubmit && fileTarget.status !== 'approved'}
          onClose={() => setFileFor(null)}
          onChanged={reload}
        />
      )}
    </Card>
  );
}

/**
 * Tab "Lịch sử" — TỔNG HỢP mọi thao tác tệp trong kho biểu mẫu
 * (biểu mẫu gốc + minh chứng đã nộp), mới nhất trước.
 * Trước đây phải mở từng biểu mẫu mới xem được lịch sử riêng của nó.
 */
function HistoryTab() {
  const toast = useToast();
  const [q, setQ] = useState('');
  // Chỉ gọi API khi người dùng ngừng gõ — xem useDebounced (R5.3).
  const dq = useDebounced(q);
  const [scope, setScope] = useState('');
  const [action, setAction] = useState('');
  const { data, loading } = useAsync(
    () => formsApi.listFormsHistory({ q: dq || undefined, owner_type: scope || undefined, limit: 200 }),
    [dq, scope],
  );
  // Lọc theo loại thao tác ở client (nguồn đã gọn, tránh thêm tham số API)
  const rows = (data?.data ?? []).filter((r) => !action || r.action.endsWith(action));

  const ACTION_TONE: Record<string, BadgeTone> = {
    'Tải lên': 'success',
    'Thay tệp': 'warning',
    'Gỡ tệp': 'overdue',
  };

  const columns: Column<formsApi.FormHistoryItem>[] = [
    {
      key: 'at', header: 'Thời gian', priority: 1,
      sortValue: (r) => r.at,
      render: (r) => <span className="whitespace-nowrap text-subink">{formatDateTime(r.at)}</span>,
    },
    {
      key: 'action', header: 'Thao tác', priority: 1,
      render: (r) => <Badge tone={ACTION_TONE[r.action_label] ?? 'neutral'}>{r.action_label}</Badge>,
    },
    {
      key: 'form', header: 'Biểu mẫu',
      render: (r) => (
        <div className="min-w-0">
          <div className="truncate font-medium text-ink">{r.form_code ?? '—'}</div>
          {r.form_title && <div className="truncate text-xs text-subink">{r.form_title}</div>}
        </div>
      ),
    },
    {
      key: 'scope', header: 'Loại',
      render: (r) => (
        <div className="min-w-0">
          <Badge tone={r.owner_type === 'form_template' ? 'info' : 'pending'}>{r.owner_label}</Badge>
          {r.department_name && <div className="mt-0.5 truncate text-xs text-subink">{r.department_name}</div>}
        </div>
      ),
    },
    {
      key: 'file', header: 'Tệp',
      render: (r) => <span className="break-all text-subink">{r.file_name ?? '—'}</span>,
    },
    { key: 'user', header: 'Người thực hiện', render: (r) => r.user_name ?? '—' },
    {
      key: 'reason', header: 'Lý do',
      render: (r) => <span className="text-subink">{r.reason ?? '—'}</span>,
    },
    {
      key: 'dl', header: '', align: 'right',
      render: (r) =>
        r.attachment_id ? (
          <button
            title="Tải đúng bản tệp của thao tác này (kể cả bản đã bị thay)"
            className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-blueberry hover:underline"
            onClick={() =>
              formsApi
                .openHistoryFile(
                  r.owner_type === 'form_template' ? 'templates' : 'submissions',
                  r.owner_id,
                  r.attachment_id!,
                )
                .catch((e) => toast.error(describeError(e).title))
            }
          >
            <Download size={14} /> Tải bản này
          </button>
        ) : (
          <span className="text-subink">—</span>
        ),
    },
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
        <SearchInput value={q} onChange={setQ} placeholder="Mã biểu mẫu / tệp / người…" className="w-full sm:max-w-xs" />
        <Select value={scope} onChange={(e) => setScope(e.target.value)} className="w-full sm:max-w-[210px]">
          <option value="">— Mọi phạm vi —</option>
          <option value="form_template">Biểu mẫu gốc</option>
          <option value="form_submission">Minh chứng đã nộp</option>
        </Select>
        <Select value={action} onChange={(e) => setAction(e.target.value)} className="w-full sm:max-w-[180px]">
          <option value="">— Mọi thao tác —</option>
          <option value="_UPLOAD">Tải lên</option>
          <option value="_REPLACE">Thay tệp</option>
          <option value="_DELETE">Gỡ tệp</option>
        </Select>
        <span className="ml-auto text-sm text-subink">{rows.length} thao tác</span>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        loading={loading}
        pageSize={20}
        empty={
          <EmptyState
            title="Chưa có thay đổi tệp nào"
            description="Mọi lần tải lên / thay / gỡ tệp trong kho biểu mẫu VILAS sẽ được ghi lại ở đây."
          />
        }
      />
    </Card>
  );
}
