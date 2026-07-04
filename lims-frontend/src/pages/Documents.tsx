import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Plus, BarChart3, ClipboardCheck, UploadCloud } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { DocVersionStatusBadge, SecurityLevelBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canApproveDocuments, canManageDocuments, canViewDocumentStats } from '@/lib/rbac';
import type { DocumentListItem, DocumentType, SecurityLevel } from '@/types';
import * as docsApi from '@/api/documents';
import * as usersApi from '@/api/users';

const MAX_FILE_MB = 20;
const ACCEPT = '.pdf,.docx,.xlsx,.png,.jpg,.jpeg';

export function Documents() {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [securityLevel, setSecurityLevel] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const { data, loading } = useAsync(
    () =>
      docsApi.listDocuments({
        q: q || undefined,
        type: type || undefined,
        security_level: securityLevel || undefined,
        department_id: departmentId || undefined,
        limit: 100,
      }),
    [q, type, securityLevel, departmentId],
  );
  const { data: types } = useAsync(() => docsApi.listDocumentTypes(), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  const canManage = canManageDocuments(user);

  const columns: Column<DocumentListItem>[] = [
    {
      key: 'document_code',
      header: 'Mã / Tiêu đề',
      sortValue: (d) => d.document_code,
      render: (d) => (
        <div>
          <p className="font-semibold text-ink">{d.title}</p>
          <p className="text-xs text-subink">{d.document_code}</p>
        </div>
      ),
    },
    { key: 'type', header: 'Loại', render: (d) => <Badge tone="info">{d.type_label}</Badge> },
    { key: 'department', header: 'Phòng', render: (d) => d.department_name ?? '—' },
    {
      key: 'security',
      header: 'Bảo mật',
      align: 'center',
      render: (d) => <SecurityLevelBadge level={d.security_level} />,
    },
    {
      key: 'version',
      header: 'Hiệu lực',
      render: (d) =>
        d.current_version ? (
          <span className="inline-flex items-center gap-2">
            <span className="font-medium text-ink">v{d.current_version.version_no}</span>
            <DocVersionStatusBadge status={d.current_version.status} />
          </span>
        ) : (
          <Badge tone="muted">Chưa ban hành</Badge>
        ),
    },
    {
      key: 'created_at',
      header: 'Ngày tạo',
      sortValue: (d) => d.created_at,
      render: (d) => formatDate(d.created_at),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Tài liệu"
        description="Kiểm soát tài liệu & hồ sơ theo ISO/IEC 17025 (§8.3 — quy trình duyệt và ban hành)"
        icon={<FileText size={20} />}
        actions={
          <div className="flex items-center gap-2">
            {canApproveDocuments(user) && (
              <Button variant="secondary" onClick={() => navigate('/documents/pending')}>
                <ClipboardCheck size={16} /> Chờ duyệt
              </Button>
            )}
            {canViewDocumentStats(user) && (
              <Button variant="secondary" onClick={() => navigate('/documents/stats')}>
                <BarChart3 size={16} /> Thống kê
              </Button>
            )}
            {canManage && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} /> Tạo tài liệu
              </Button>
            )}
          </div>
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Mã hoặc tiêu đề…" className="max-w-xs flex-1" />
          <Select value={type} onChange={(e) => setType(e.target.value)} className="max-w-[200px]">
            <option value="">Mọi loại</option>
            {(types ?? []).map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </Select>
          <Select
            value={securityLevel}
            onChange={(e) => setSecurityLevel(e.target.value)}
            className="max-w-[160px]"
          >
            <option value="">Mọi mức bảo mật</option>
            <option value="internal">Nội bộ</option>
            <option value="restricted">Hạn chế</option>
          </Select>
          <Select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="max-w-[200px]"
          >
            <option value="">Mọi phòng</option>
            {(depts?.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(d) => d.id}
          onRowClick={(d) => navigate(`/documents/${d.id}`)}
          loading={loading}
          pageSize={12}
        />
      </Card>

      {createOpen && (
        <CreateDocumentModal
          types={types ?? []}
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => {
            setCreateOpen(false);
            toast.success('Đã tạo tài liệu và phiên bản đầu (nháp)');
            navigate(`/documents/${id}`);
          }}
        />
      )}
    </div>
  );
}

function CreateDocumentModal({
  types,
  onClose,
  onCreated,
}: {
  types: { code: DocumentType; label: string }[];
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [departmentId, setDepartmentId] = useState(user?.department?.id ?? '');
  const [security, setSecurity] = useState<SecurityLevel>('internal');
  const [changeNote, setChangeNote] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // admin/leader chọn phòng; staff cố định phòng mình.
  const canPickDept = user?.role === 'admin' || user?.role === 'leader';
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề tài liệu');
    if (!type) return toast.error('Chọn loại tài liệu');
    if (!file) return toast.error('Chọn tệp nội dung phiên bản đầu');
    if (file.size > MAX_FILE_MB * 1024 * 1024)
      return toast.error(`Tệp vượt quá ${MAX_FILE_MB}MB`);
    setSubmitting(true);
    try {
      const res = await docsApi.createDocument({
        title: title.trim(),
        type,
        department_id: canPickDept ? departmentId || undefined : undefined,
        security_level: security,
        change_note: changeNote.trim() || undefined,
        file,
      });
      onCreated(res.id);
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
      title="Tạo tài liệu mới"
      description="Tài liệu sẽ tạo kèm phiên bản đầu (v1) ở trạng thái nháp — gửi duyệt sau khi hoàn tất."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Hủy
          </Button>
          <Button onClick={submit} loading={submitting}>
            Tạo tài liệu
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tiêu đề" required className="sm:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="vd: SOP đo pH" />
        </Field>
        <Field label="Loại tài liệu" required>
          <Select value={type} onChange={(e) => setType(e.target.value as DocumentType)}>
            <option value="">— Chọn —</option>
            {types.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Mức bảo mật" required>
          <Select value={security} onChange={(e) => setSecurity(e.target.value as SecurityLevel)}>
            <option value="internal">Nội bộ</option>
            <option value="restricted">Hạn chế (chỉ phòng sở hữu + lãnh đạo)</option>
          </Select>
        </Field>
        {canPickDept ? (
          <Field label="Phòng ban sở hữu" className="sm:col-span-2">
            <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">— Mặc định theo người tạo —</option>
              {(depts?.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Phòng ban sở hữu" className="sm:col-span-2" hint="Tài liệu thuộc phòng của bạn.">
            <Input value={user?.department?.name ?? '—'} disabled />
          </Field>
        )}
        <Field label="Ghi chú phiên bản" className="sm:col-span-2" hint="Không bắt buộc cho phiên bản đầu.">
          <Textarea
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            placeholder="vd: Phiên bản ban hành lần đầu"
          />
        </Field>
        <Field label="Tệp nội dung (v1)" required className="sm:col-span-2" hint="PDF, DOCX, XLSX, PNG, JPG · tối đa 20MB">
          <FileDrop file={file} onSelect={setFile} />
        </Field>
      </div>
    </Modal>
  );
}

/** Ô chọn tệp dùng chung (tạo tài liệu / version). */
export function FileDrop({
  file,
  onSelect,
  accept = ACCEPT,
}: {
  file: File | null;
  onSelect: (f: File | null) => void;
  accept?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-hairline bg-plate/40 px-4 py-3 text-sm hover:bg-plate">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blueberry/10 text-blueberry">
        <UploadCloud size={18} />
      </span>
      <span className="min-w-0 flex-1">
        {file ? (
          <span className="truncate font-medium text-ink">{file.name}</span>
        ) : (
          <span className="text-subink">Bấm để chọn tệp…</span>
        )}
      </span>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
