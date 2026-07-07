import { useState } from 'react';
import { Lightbulb, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { DescList, DescItem } from '@/components/ui/DescList';
import { ImprovementStatusBadge } from '@/components/ui/StatusBadge';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canCreateImprovement, canManageRisk } from '@/lib/rbac';
import {
  IMPROVEMENT_SOURCE_LABELS,
  IMPROVEMENT_STATUS_LABELS,
  type ImprovementItem,
  type ImprovementSource,
  type ImprovementStatus,
} from '@/types';
import * as riskApi from '@/api/risks';

export function Improvements() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<ImprovementStatus | ''>('');
  const [source, setSource] = useState<ImprovementSource | ''>('');
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<ImprovementItem | null>(null);

  const { data, loading, reload } = useAsync(
    () => riskApi.listImprovements({ q: q || undefined, status: status || undefined, source: source || undefined, limit: 100 }),
    [q, status, source],
  );

  const columns: Column<ImprovementItem>[] = [
    {
      key: 'code',
      header: 'Mã / Tiêu đề',
      sortValue: (i) => i.improvement_code,
      render: (i) => (
        <div>
          <p className="font-semibold text-ink">{i.title}</p>
          <p className="text-xs text-subink">{i.improvement_code}</p>
        </div>
      ),
    },
    { key: 'source', header: 'Nguồn', render: (i) => <Badge tone="neutral">{IMPROVEMENT_SOURCE_LABELS[i.source]}</Badge> },
    { key: 'status', header: 'Trạng thái', align: 'center', render: (i) => <ImprovementStatusBadge status={i.status} /> },
    { key: 'owner', header: 'Phụ trách', render: (i) => i.owner_name ?? '—' },
    { key: 'created', header: 'Ngày ghi nhận', sortValue: (i) => i.created_at, render: (i) => formatDate(i.created_at) },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Cơ hội cải tiến"
        description="Ghi nhận và theo dõi cơ hội cải tiến liên tục theo ISO/IEC 17025 (§8.6)"
        icon={<Lightbulb size={20} />}
        actions={
          canCreateImprovement(user) && (
            <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Ghi nhận cải tiến</Button>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Mã hoặc tiêu đề…" className="max-w-xs flex-1" />
          <Select value={source} onChange={(e) => setSource(e.target.value as ImprovementSource | '')} className="max-w-[180px]">
            <option value="">Mọi nguồn</option>
            {(Object.keys(IMPROVEMENT_SOURCE_LABELS) as ImprovementSource[]).map((s) => (
              <option key={s} value={s}>{IMPROVEMENT_SOURCE_LABELS[s]}</option>
            ))}
          </Select>
          <Select value={status} onChange={(e) => setStatus(e.target.value as ImprovementStatus | '')} className="max-w-[180px]">
            <option value="">Mọi trạng thái</option>
            {(Object.keys(IMPROVEMENT_STATUS_LABELS) as ImprovementStatus[]).map((s) => (
              <option key={s} value={s}>{IMPROVEMENT_STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(i) => i.id}
          onRowClick={(i) => setSelected(i)}
          loading={loading}
          pageSize={12}
        />
      </Card>

      {createOpen && <CreateModal onClose={() => setCreateOpen(false)} onDone={() => { setCreateOpen(false); reload(); toast.success('Đã ghi nhận cải tiến'); }} />}
      {selected && (
        <DetailModal
          item={selected}
          canManage={canManageRisk(user)}
          onClose={() => setSelected(null)}
          onDone={() => { setSelected(null); reload(); }}
        />
      )}
    </div>
  );
}

function CreateModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [source, setSource] = useState<ImprovementSource>('staff');
  const [submitting, setSubmitting] = useState(false);
  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề');
    if (!description.trim()) return toast.error('Nhập mô tả');
    setSubmitting(true);
    try {
      await riskApi.createImprovement({ title: title.trim(), description: description.trim(), source });
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Modal open onClose={onClose} size="lg" title="Ghi nhận cơ hội cải tiến"
      footer={<><Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button><Button onClick={submit} loading={submitting}>Ghi nhận</Button></>}>
      <div className="flex flex-col gap-4">
        <Field label="Nguồn">
          <Select value={source} onChange={(e) => setSource(e.target.value as ImprovementSource)}>
            {(Object.keys(IMPROVEMENT_SOURCE_LABELS) as ImprovementSource[]).map((s) => (
              <option key={s} value={s}>{IMPROVEMENT_SOURCE_LABELS[s]}</option>
            ))}
          </Select>
        </Field>
        <Field label="Tiêu đề" required><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Mô tả" required><Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} /></Field>
      </div>
    </Modal>
  );
}

function DetailModal({ item, canManage, onClose, onDone }: { item: ImprovementItem; canManage: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [status, setStatus] = useState<ImprovementStatus>(item.status);
  const [saving, setSaving] = useState(false);
  async function save() {
    setSaving(true);
    try {
      await riskApi.updateImprovement(item.id, { status });
      toast.success('Đã cập nhật');
      onDone();
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal open onClose={onClose} size="lg" title={item.title} description={item.improvement_code}
      footer={
        canManage ? (
          <>
            <Button variant="secondary" onClick={onClose} disabled={saving}>Đóng</Button>
            <Button onClick={save} loading={saving} disabled={status === item.status}>Lưu trạng thái</Button>
          </>
        ) : (
          <Button variant="secondary" onClick={onClose}>Đóng</Button>
        )
      }>
      <DescList>
        <DescItem label="Nguồn" value={IMPROVEMENT_SOURCE_LABELS[item.source]} />
        <DescItem label="Mô tả" value={<span className="whitespace-pre-wrap">{item.description}</span>} />
        <DescItem label="Phụ trách" value={item.owner_name} />
        <DescItem label="Ngày ghi nhận" value={formatDate(item.created_at)} />
        <DescItem label="Liên kết NC/CAPA" value={item.linked_nc_id ? 'Đã liên kết' : null} />
      </DescList>
      {canManage && (
        <div className="mt-4 border-t border-hairline pt-4">
          <Field label="Cập nhật trạng thái">
            <Select value={status} onChange={(e) => setStatus(e.target.value as ImprovementStatus)}>
              {(Object.keys(IMPROVEMENT_STATUS_LABELS) as ImprovementStatus[]).map((s) => (
                <option key={s} value={s}>{IMPROVEMENT_STATUS_LABELS[s]}</option>
              ))}
            </Select>
          </Field>
        </div>
      )}
    </Modal>
  );
}
