import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Plus, PlayCircle } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import { RiskKindBadge, RiskStatusBadge, RiskBandBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import { formatDate } from '@/lib/format';
import { canCreateRisk, canRunRiskCron } from '@/lib/rbac';
import {
  RISK_KIND_LABELS,
  RISK_STATUS_LABELS,
  type RiskBand,
  type RiskKind,
  type RiskListItem,
  type RiskStats,
  type RiskStatus,
} from '@/types';
import * as riskApi from '@/api/risks';
import * as usersApi from '@/api/users';

export function Risks() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [kind, setKind] = useState<RiskKind | ''>('');
  const [status, setStatus] = useState<RiskStatus | ''>('');
  const [band, setBand] = useState<RiskBand | ''>('');
  const [createOpen, setCreateOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);

  const { data, loading } = useAsync(
    () => riskApi.listRisks({ q: q || undefined, kind: kind || undefined, status: status || undefined, band: band || undefined, limit: 100 }),
    [q, kind, status, band],
  );
  const { data: stats, reload: reloadStats } = useAsync(() => riskApi.getRiskStats(), []);

  const columns: Column<RiskListItem>[] = [
    {
      key: 'risk_code',
      header: 'Mã / Tiêu đề',
      sortValue: (r) => r.risk_code,
      render: (r) => (
        <div>
          <p className="font-semibold text-ink">{r.title}</p>
          <p className="text-xs text-subink">{r.risk_code}</p>
        </div>
      ),
    },
    { key: 'kind', header: 'Loại', align: 'center', render: (r) => <RiskKindBadge kind={r.kind} /> },
    {
      key: 'level',
      header: 'Mức rủi ro (P×I)',
      sortValue: (r) => r.level,
      render: (r) => <RiskBandBadge band={r.band} level={r.level} />,
    },
    { key: 'status', header: 'Trạng thái', align: 'center', render: (r) => <RiskStatusBadge status={r.status} /> },
    { key: 'owner', header: 'Phụ trách', render: (r) => r.owner_name ?? '—' },
    {
      key: 'review',
      header: 'Đánh giá lại',
      sortValue: (r) => r.next_review_date ?? '',
      render: (r) => formatDate(r.next_review_date ?? undefined),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Rủi ro & Cơ hội"
        description="Sổ đăng ký rủi ro/cơ hội và ma trận đánh giá theo ISO/IEC 17025 (§8.5)"
        icon={<AlertTriangle size={20} />}
        actions={
          <div className="flex items-center gap-2">
            {canRunRiskCron(user) && (
              <Button variant="secondary" onClick={() => setCronOpen(true)}>
                <PlayCircle size={16} /> Nhắc đánh giá lại
              </Button>
            )}
            {canCreateRisk(user) && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} /> Thêm rủi ro
              </Button>
            )}
          </div>
        }
      />

      {stats && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Ma trận rủi ro (5×5)" subtitle="Khả năng xảy ra × Mức tác động — chỉ tính rủi ro đang mở" />
            <CardBody>
              <RiskMatrix stats={stats} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Tổng quan" />
            <CardBody className="flex flex-col gap-2.5">
              <SummaryRow label="Tổng đang theo dõi" value={stats.total} />
              <SummaryRow label="Mức cao" value={stats.by_band.high} tone="overdue" />
              <SummaryRow label="Mức trung bình" value={stats.by_band.medium} tone="warning" />
              <SummaryRow label="Mức thấp" value={stats.by_band.low} tone="success" />
              <SummaryRow label="Đã đóng" value={stats.by_status.closed ?? 0} />
            </CardBody>
          </Card>
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
          <SearchInput value={q} onChange={setQ} placeholder="Mã hoặc tiêu đề…" className="max-w-xs flex-1" />
          <Select value={kind} onChange={(e) => setKind(e.target.value as RiskKind | '')} className="max-w-[150px]">
            <option value="">Rủi ro & cơ hội</option>
            {(Object.keys(RISK_KIND_LABELS) as RiskKind[]).map((k) => (
              <option key={k} value={k}>{RISK_KIND_LABELS[k]}</option>
            ))}
          </Select>
          <Select value={band} onChange={(e) => setBand(e.target.value as RiskBand | '')} className="max-w-[150px]">
            <option value="">Mọi mức</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
            <option value="low">Thấp</option>
          </Select>
          <Select value={status} onChange={(e) => setStatus(e.target.value as RiskStatus | '')} className="max-w-[170px]">
            <option value="">Mọi trạng thái</option>
            {(Object.keys(RISK_STATUS_LABELS) as RiskStatus[]).map((s) => (
              <option key={s} value={s}>{RISK_STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.data ?? []}
          rowKey={(r) => r.id}
          onRowClick={(r) => navigate(`/risks/${r.id}`)}
          loading={loading}
          pageSize={12}
        />
      </Card>

      {createOpen && (
        <CreateRiskModal onClose={() => setCreateOpen(false)} onCreated={(id) => { setCreateOpen(false); navigate(`/risks/${id}`); }} />
      )}
      {cronOpen && (
        <RunCronModal onClose={() => setCronOpen(false)} onDone={() => { setCronOpen(false); reloadStats(); }} />
      )}
    </div>
  );
}

function bandOf(level: number): RiskBand {
  if (level <= 4) return 'low';
  if (level <= 12) return 'medium';
  return 'high';
}
const BAND_BG: Record<RiskBand, string> = {
  low: 'bg-success/15 text-success',
  medium: 'bg-warning/15 text-[#b45309]',
  high: 'bg-overdue/15 text-overdue',
};

function RiskMatrix({ stats }: { stats: RiskStats }) {
  // rows: likelihood 5→1 (top to bottom); cols: impact 1→5
  const likelihoods = [5, 4, 3, 2, 1];
  const impacts = [1, 2, 3, 4, 5];
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid grid-cols-[auto_repeat(5,minmax(44px,1fr))] gap-1 text-center text-xs">
        <div />
        {impacts.map((im) => (
          <div key={`h${im}`} className="pb-1 font-semibold text-subink">
            T{im}
          </div>
        ))}
        {likelihoods.map((lk) => (
          <RowCells key={`r${lk}`} lk={lk} impacts={impacts} stats={stats} />
        ))}
        <div />
        <div className="col-span-5 pt-1 text-[11px] text-subink">Mức tác động (Impact) →</div>
      </div>
      <p className="mt-2 text-[11px] text-subink">K = Khả năng xảy ra · T = Mức tác động · số = số rủi ro đang mở</p>
    </div>
  );
}

function RowCells({ lk, impacts, stats }: { lk: number; impacts: number[]; stats: RiskStats }) {
  return (
    <>
      <div className="flex items-center pr-1 font-semibold text-subink">K{lk}</div>
      {impacts.map((im) => {
        const count = stats.matrix?.[lk]?.[im] ?? 0;
        const band = bandOf(lk * im);
        return (
          <div
            key={`${lk}-${im}`}
            className={`flex h-11 items-center justify-center rounded-md font-bold ${BAND_BG[band]} ${count === 0 ? 'opacity-40' : ''}`}
            title={`Khả năng ${lk} × Tác động ${im} = ${lk * im}`}
          >
            {count}
          </div>
        );
      })}
    </>
  );
}

function SummaryRow({ label, value, tone }: { label: string; value: number; tone?: 'overdue' | 'warning' | 'success' }) {
  const color = tone === 'overdue' ? 'text-overdue' : tone === 'warning' ? 'text-[#b45309]' : tone === 'success' ? 'text-success' : 'text-ink';
  return (
    <div className="flex items-center justify-between border-b border-hairline pb-2 last:border-0">
      <span className="text-sm text-subink">{label}</span>
      <span className={`text-lg font-bold ${color}`}>{value}</span>
    </div>
  );
}

function CreateRiskModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [kind, setKind] = useState<RiskKind>('risk');
  const [likelihood, setLikelihood] = useState(3);
  const [impact, setImpact] = useState(3);
  const [processRef, setProcessRef] = useState('');
  const [reviewDate, setReviewDate] = useState('');
  const [departmentId, setDepartmentId] = useState(user?.department?.id ?? '');
  const [submitting, setSubmitting] = useState(false);
  const canPickDept = user?.role === 'admin' || user?.role === 'leader';
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);
  const level = likelihood * impact;
  const band = bandOf(level);

  async function submit() {
    if (!title.trim()) return toast.error('Nhập tiêu đề');
    if (!context.trim()) return toast.error('Nhập bối cảnh');
    setSubmitting(true);
    try {
      const res = await riskApi.createRisk({
        title: title.trim(), context: context.trim(), kind, likelihood, impact,
        process_ref: processRef.trim() || null,
        department_id: canPickDept ? departmentId || undefined : undefined,
        next_review_date: reviewDate || null,
      });
      toast.success(`Đã tạo ${res.risk_code}`);
      onCreated(res.id);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open onClose={onClose} size="lg"
      title="Thêm rủi ro / cơ hội"
      description="Mức rủi ro = Khả năng × Tác động (thang 1–5). Mã do hệ thống tự sinh."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>Hủy</Button>
          <Button onClick={submit} loading={submitting}>Tạo</Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Loại">
          <Select value={kind} onChange={(e) => setKind(e.target.value as RiskKind)}>
            {(Object.keys(RISK_KIND_LABELS) as RiskKind[]).map((k) => (
              <option key={k} value={k}>{RISK_KIND_LABELS[k]}</option>
            ))}
          </Select>
        </Field>
        <Field label="Tiến trình liên quan">
          <Input value={processRef} onChange={(e) => setProcessRef(e.target.value)} placeholder="vd: Tiếp nhận mẫu" />
        </Field>
        <Field label="Tiêu đề" required className="sm:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="vd: Mẫu bị nhiễm chéo khi lưu" />
        </Field>
        <Field label="Bối cảnh / mô tả" required className="sm:col-span-2">
          <Textarea value={context} onChange={(e) => setContext(e.target.value)} rows={2} />
        </Field>
        <Field label="Khả năng xảy ra (1–5)">
          <Select value={String(likelihood)} onChange={(e) => setLikelihood(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field label="Mức tác động (1–5)">
          <Select value={String(impact)} onChange={(e) => setImpact(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field label="Mức rủi ro tính được" className="sm:col-span-2">
          <div className={`inline-flex items-center rounded-lg px-3 py-2 text-sm font-bold ${BAND_BG[band]}`}>
            {level} — {band === 'high' ? 'Cao' : band === 'medium' ? 'Trung bình' : 'Thấp'}
          </div>
        </Field>
        {canPickDept && (
          <Field label="Phòng ban" className="sm:col-span-2">
            <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">— Mặc định theo người tạo —</option>
              {(depts?.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
          </Field>
        )}
        <Field label="Ngày đánh giá lại" className="sm:col-span-2">
          <Input type="date" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function RunCronModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [asOf, setAsOf] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<riskApi.RunRiskReviewDueResult | null>(null);

  async function run() {
    setRunning(true);
    try {
      const res = await riskApi.runRiskReviewCron(asOf || undefined);
      setResult(res);
      toast.success(`Đã tạo ${res.notifications_created} thông báo`);
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Modal
      open onClose={onClose}
      title="Nhắc đánh giá lại rủi ro (CRON-8)"
      description="Quét rủi ro tới mốc 30/15/7 ngày và gửi thông báo cho người phụ trách."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={running}>{result ? 'Đóng' : 'Hủy'}</Button>
          {!result && <Button onClick={run} loading={running}>Chạy ngay</Button>}
        </>
      }
    >
      {result ? (
        <div className="text-sm text-ink">
          Quét {result.scanned_risks} rủi ro · tạo {result.notifications_created} thông báo · khử trùng {result.deduped}.
          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={onDone}>Tải lại</Button>
          </div>
        </div>
      ) : (
        <Field label="Mốc thời gian (tùy chọn — chỉ test)" hint="Bỏ trống để dùng hôm nay.">
          <Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </Field>
      )}
    </Modal>
  );
}
