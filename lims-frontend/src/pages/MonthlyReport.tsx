import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarClock,
  Plus,
  Trash2,
  Presentation,
  FolderKanban,
  BookText,
  FileSignature,
  Landmark,
  ArrowLeft,
  Save,
  RotateCcw,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Input, Textarea, Select } from '@/components/ui/Field';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { describeError } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import * as reportApi from '@/api/activityReport';
import type {
  TeachingEntry,
  ProjectEntry,
  PublicationEntry,
  ContractEntry,
  OtherEntry,
  PubKind,
  OtherKind,
} from '@/api/activityReport';

const PUB_KIND_LABELS: Record<PubKind, string> = {
  domestic: 'Trong nước',
  international: 'Quốc tế',
  conference: 'Hội nghị / Kỷ yếu',
};
const OTHER_KIND_LABELS: Record<OtherKind, string> = {
  dang: 'Công tác Đảng',
  cong_doan: 'Công đoàn',
  vilas: 'VILAS / QLCL',
  khac: 'Khác',
};
const PROJECT_LEVELS: { value: string; label: string }[] = [
  { value: 'university', label: 'Cấp trường' },
  { value: 'ministry', label: 'Cấp bộ' },
  { value: 'province', label: 'Cấp tỉnh' },
  { value: 'national', label: 'Cấp nhà nước' },
  { value: 'international', label: 'Quốc tế' },
  { value: 'other', label: 'Khác' },
];

/** Kỳ báo cáo mặc định = tháng hiện tại "MM/YYYY". */
function defaultPeriod(): string {
  const d = new Date();
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
}
function defaultAcademicYear(): string {
  const d = new Date();
  const y = d.getFullYear();
  // Năm học bắt đầu tháng 8 (VN): >= tháng 8 → y-(y+1), ngược lại (y-1)-y.
  return d.getMonth() + 1 >= 8 ? `${y}-${y + 1}` : `${y - 1}-${y}`;
}

// Danh sách tháng "01".."12" + năm/năm học để chọn (có kèm giá trị hiện tại nếu nằm ngoài phạm vi).
const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'));
function periodYearOptions(current?: string): string[] {
  const y = new Date().getFullYear();
  const base = [y + 1, y, y - 1, y - 2].map(String);
  if (current && !base.includes(current)) base.unshift(current);
  return base;
}
function academicYearOptions(current?: string): string[] {
  const d = new Date();
  const s0 = d.getMonth() + 1 >= 8 ? d.getFullYear() : d.getFullYear() - 1;
  const base: string[] = [];
  for (let s = s0 + 1; s >= s0 - 2; s--) base.push(`${s}-${s + 1}`);
  if (current && !base.includes(current)) base.unshift(current);
  return base;
}
const CUR_MONTH = String(new Date().getMonth() + 1).padStart(2, '0');
const CUR_YEAR = String(new Date().getFullYear());

// ── Tự động lưu nháp (localStorage) — chống mất dữ liệu khi reload / đóng tab ──
const DRAFT_PREFIX = 'lims_activity_report_draft:';

interface Draft {
  periodLabel: string;
  academicYear: string;
  note: string;
  teaching: TeachingEntry[];
  projects: ProjectEntry[];
  publications: PublicationEntry[];
  contracts: ContractEntry[];
  activities: OtherEntry[];
  savedAt: string;
}

function loadDraft(key: string): Draft | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const d = JSON.parse(raw) as Draft;
    // sanity: đủ các mảng section
    if (!Array.isArray(d.teaching) || !Array.isArray(d.publications)) return null;
    return d;
  } catch {
    return null;
  }
}

interface SectionProps {
  icon: React.ReactNode;
  title: string;
  hint: string;
  count: number;
  onAdd: () => void;
  children: React.ReactNode;
}
function Section({ icon, title, hint, count, onAdd, children }: SectionProps) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-plate text-blueberry">{icon}</span>
        <div className="flex-1">
          <div className="text-sm font-semibold text-ink">{title} {count > 0 && <span className="text-subink">({count})</span>}</div>
          <div className="text-xs text-subink">{hint}</div>
        </div>
        <Button size="sm" variant="secondary" onClick={onAdd}><Plus size={14} /> Thêm dòng</Button>
      </div>
      {count === 0 ? (
        <div className="p-4 text-sm text-subink">Chưa có dòng nào. Bấm "Thêm dòng" nếu tháng này có hoạt động.</div>
      ) : (
        <div className="flex flex-col divide-y divide-hairline">{children}</div>
      )}
    </Card>
  );
}

function RowShell({ onRemove, children }: { onRemove: () => void; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 p-4">
      <div className="grid flex-1 gap-3 md:grid-cols-2 lg:grid-cols-4">{children}</div>
      <Button size="sm" variant="ghost" onClick={onRemove} className="mt-1"><Trash2 size={14} className="text-overdue" /></Button>
    </div>
  );
}

export function MonthlyReport() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  // Khóa nháp theo user để không lẫn nháp giữa các tài khoản trên cùng máy.
  const draftKey = DRAFT_PREFIX + (user?.id ?? 'anon');
  // Nạp nháp MỘT LẦN lúc mount (useRef để không nạp lại mỗi render).
  const initial = useRef<Draft | null>(loadDraft(draftKey)).current;

  const [periodLabel, setPeriodLabel] = useState(initial?.periodLabel ?? defaultPeriod());
  const [academicYear, setAcademicYear] = useState(initial?.academicYear ?? defaultAcademicYear());
  const [note, setNote] = useState(initial?.note ?? '');
  const [teaching, setTeaching] = useState<TeachingEntry[]>(initial?.teaching ?? []);
  const [projects, setProjects] = useState<ProjectEntry[]>(initial?.projects ?? []);
  const [publications, setPublications] = useState<PublicationEntry[]>(initial?.publications ?? []);
  const [contracts, setContracts] = useState<ContractEntry[]>(initial?.contracts ?? []);
  const [activities, setActivities] = useState<OtherEntry[]>(initial?.activities ?? []);
  const [submitting, setSubmitting] = useState(false);
  const [restoredAt, setRestoredAt] = useState<string | null>(initial?.savedAt ?? null);
  const [savedAt, setSavedAt] = useState<string | null>(initial?.savedAt ?? null);
  // Cờ để bỏ ghi nháp sau khi nộp thành công (tránh effect ghi lại nháp đã xóa).
  const submittedRef = useRef(false);

  function up<T>(setter: React.Dispatch<React.SetStateAction<T[]>>, i: number, patch: Partial<T>) {
    setter((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function rm<T>(setter: React.Dispatch<React.SetStateAction<T[]>>, i: number) {
    setter((rows) => rows.filter((_, idx) => idx !== i));
  }

  const total = teaching.length + projects.length + publications.length + contracts.length + activities.length;
  const hasContent = total > 0 || note.trim() !== '';

  // Tự động lưu nháp (debounce 500ms) mỗi khi form đổi. Nếu form trống → xóa nháp.
  useEffect(() => {
    if (submittedRef.current) return;
    const id = setTimeout(() => {
      try {
        if (!hasContent) {
          localStorage.removeItem(draftKey);
          setSavedAt(null);
          return;
        }
        const now = new Date().toISOString();
        const draft: Draft = {
          periodLabel, academicYear, note,
          teaching, projects, publications, contracts, activities,
          savedAt: now,
        };
        localStorage.setItem(draftKey, JSON.stringify(draft));
        setSavedAt(now);
      } catch {
        /* localStorage đầy / bị chặn — bỏ qua, không chặn nhập liệu */
      }
    }, 500);
    return () => clearTimeout(id);
  }, [draftKey, hasContent, periodLabel, academicYear, note, teaching, projects, publications, contracts, activities]);

  // Cảnh báo trước khi rời trang nếu còn dữ liệu chưa nộp (đóng tab / reload).
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (hasContent && !submittedRef.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    }
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [hasContent]);

  function discardDraft() {
    localStorage.removeItem(draftKey);
    setPeriodLabel(defaultPeriod());
    setAcademicYear(defaultAcademicYear());
    setNote('');
    setTeaching([]);
    setProjects([]);
    setPublications([]);
    setContracts([]);
    setActivities([]);
    setRestoredAt(null);
    setSavedAt(null);
    toast.success('Đã xóa bản nháp');
  }

  async function submit() {
    if (!periodLabel.trim()) return toast.error('Nhập kỳ báo cáo (VD: 07/2026)');
    if (total === 0) return toast.error('Báo cáo trống — thêm ít nhất một dòng hoạt động');
    // validate bắt buộc
    if (teaching.some((t) => !t.course_name.trim())) return toast.error('Môn giảng dạy: thiếu tên môn');
    if (projects.some((p) => !p.title.trim())) return toast.error('Đề tài: thiếu tên đề tài');
    if (publications.some((p) => !p.title.trim())) return toast.error('Bài báo: thiếu tiêu đề');
    if (contracts.some((c) => !c.title.trim())) return toast.error('Hợp đồng: thiếu tên hợp đồng');
    if (activities.some((a) => !a.content.trim())) return toast.error('Công tác khác: thiếu nội dung');

    setSubmitting(true);
    try {
      await reportApi.createReport({
        period_label: periodLabel.trim(),
        academic_year: academicYear.trim() || null,
        note: note.trim() || null,
        teaching,
        projects,
        publications,
        contracts,
        activities,
      });
      // Nộp thành công → dọn nháp để không khôi phục lại lần sau.
      submittedRef.current = true;
      localStorage.removeItem(draftKey);
      toast.success('Đã nộp báo cáo hoạt động');
      navigate('/activity-reports');
    } catch (err) {
      const e = describeError(err);
      toast.error(e.title, e.description);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Nộp báo cáo hoạt động tháng"
        description="Điền các hoạt động của bạn trong kỳ. Sau khi nộp, văn phòng sẽ tổng hợp vào các báo cáo chung."
        icon={<CalendarClock size={20} />}
        actions={<Button variant="secondary" onClick={() => navigate('/activity-reports')}><ArrowLeft size={16} /> Danh sách</Button>}
      />

      {restoredAt && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/5 px-4 py-3 text-sm">
          <span className="flex items-center gap-2 text-ink">
            <RotateCcw size={16} className="text-warning" />
            Đã khôi phục bản nháp lưu lúc <strong>{formatDateTime(restoredAt)}</strong>. Bạn có thể tiếp tục điền và nộp.
          </span>
          <button type="button" onClick={discardDraft} className="font-medium text-overdue underline underline-offset-2">
            Xóa nháp & làm lại từ đầu
          </button>
        </div>
      )}

      <Card>
        <div className="grid gap-4 p-4 md:grid-cols-3">
          <Field label="Kỳ báo cáo" required hint="Chọn tháng và năm">
            <div className="flex gap-2">
              <Select
                value={periodLabel.split('/')[0] ?? ''}
                onChange={(e) => setPeriodLabel(`${e.target.value}/${periodLabel.split('/')[1] || CUR_YEAR}`)}
                aria-label="Tháng"
              >
                {MONTHS.map((m) => (
                  <option key={m} value={m}>Tháng {Number(m)}</option>
                ))}
              </Select>
              <Select
                value={periodLabel.split('/')[1] ?? ''}
                onChange={(e) => setPeriodLabel(`${periodLabel.split('/')[0] || CUR_MONTH}/${e.target.value}`)}
                aria-label="Năm"
              >
                {periodYearOptions(periodLabel.split('/')[1]).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </Select>
            </div>
          </Field>
          <Field label="Năm học">
            <Select value={academicYear} onChange={(e) => setAcademicYear(e.target.value)}>
              {academicYearOptions(academicYear).map((ay) => (
                <option key={ay} value={ay}>{ay}</option>
              ))}
            </Select>
          </Field>
          <Field label="Ghi chú" className="md:col-span-1">
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Tùy chọn" />
          </Field>
        </div>
      </Card>

      {/* Giảng dạy */}
      <Section icon={<Presentation size={16} />} title="Môn giảng dạy" hint="Các môn đã giảng dạy trong kỳ" count={teaching.length}
        onAdd={() => setTeaching((r) => [...r, { course_name: '' }])}>
        {teaching.map((t, i) => (
          <RowShell key={i} onRemove={() => rm(setTeaching, i)}>
            <Field label="Tên môn" required className="md:col-span-2 lg:col-span-2">
              <Input value={t.course_name} onChange={(e) => up(setTeaching, i, { course_name: e.target.value })} />
            </Field>
            <Field label="LT (HK1)"><Input type="number" min={0} value={t.hk1_theory_hours ?? ''} onChange={(e) => up(setTeaching, i, { hk1_theory_hours: e.target.value === '' ? null : Number(e.target.value) })} /></Field>
            <Field label="TH (HK1)"><Input type="number" min={0} value={t.hk1_practice_hours ?? ''} onChange={(e) => up(setTeaching, i, { hk1_practice_hours: e.target.value === '' ? null : Number(e.target.value) })} /></Field>
            <Field label="LT (HK2)"><Input type="number" min={0} value={t.hk2_theory_hours ?? ''} onChange={(e) => up(setTeaching, i, { hk2_theory_hours: e.target.value === '' ? null : Number(e.target.value) })} /></Field>
            <Field label="TH (HK2)"><Input type="number" min={0} value={t.hk2_practice_hours ?? ''} onChange={(e) => up(setTeaching, i, { hk2_practice_hours: e.target.value === '' ? null : Number(e.target.value) })} /></Field>
          </RowShell>
        ))}
      </Section>

      {/* Đề tài NCKH */}
      <Section icon={<FolderKanban size={16} />} title="Đề tài NCKH" hint="Đề tài nghiên cứu đang chủ trì / tham gia" count={projects.length}
        onAdd={() => setProjects((r) => [...r, { title: '', role: 'lead' }])}>
        {projects.map((p, i) => (
          <RowShell key={i} onRemove={() => rm(setProjects, i)}>
            <Field label="Tên đề tài" required className="md:col-span-2 lg:col-span-2">
              <Input value={p.title} onChange={(e) => up(setProjects, i, { title: e.target.value })} />
            </Field>
            <Field label="Cấp">
              <Select value={p.level ?? ''} onChange={(e) => up(setProjects, i, { level: e.target.value || null })}>
                <option value="">—</option>
                {PROJECT_LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </Select>
            </Field>
            <Field label="Vai trò">
              <Select value={p.role ?? 'lead'} onChange={(e) => up(setProjects, i, { role: e.target.value })}>
                <option value="lead">Chủ nhiệm</option>
                <option value="member">Thành viên</option>
              </Select>
            </Field>
            <Field label="Kinh phí (VNĐ)"><Input value={p.budget_amount ?? ''} onChange={(e) => up(setProjects, i, { budget_amount: e.target.value || null })} placeholder="100000000" /></Field>
          </RowShell>
        ))}
      </Section>

      {/* Bài báo */}
      <Section icon={<BookText size={16} />} title="Bài báo & Báo cáo khoa học" hint="Bài báo trong nước / quốc tế / hội nghị" count={publications.length}
        onAdd={() => setPublications((r) => [...r, { pub_kind: 'domestic', title: '' }])}>
        {publications.map((p, i) => (
          <RowShell key={i} onRemove={() => rm(setPublications, i)}>
            <Field label="Loại">
              <Select value={p.pub_kind} onChange={(e) => up(setPublications, i, { pub_kind: e.target.value as PubKind })}>
                {(Object.keys(PUB_KIND_LABELS) as PubKind[]).map((k) => <option key={k} value={k}>{PUB_KIND_LABELS[k]}</option>)}
              </Select>
            </Field>
            <Field label="Tiêu đề" required className="md:col-span-1 lg:col-span-3">
              <Input value={p.title} onChange={(e) => up(setPublications, i, { title: e.target.value })} />
            </Field>
            <Field label="Tạp chí / Kỷ yếu"><Input value={p.journal ?? ''} onChange={(e) => up(setPublications, i, { journal: e.target.value || null })} /></Field>
            <Field label="Năm"><Input type="number" value={p.year ?? ''} onChange={(e) => up(setPublications, i, { year: e.target.value === '' ? null : Number(e.target.value) })} placeholder="2026" /></Field>
            <Field label="Chỉ mục" className="lg:col-span-2">
              <div className="flex flex-wrap items-center gap-3 pt-2">
                {(['is_scie', 'is_scopus', 'is_ssci', 'is_aci'] as const).map((k) => (
                  <label key={k} className="flex items-center gap-1.5 text-sm text-ink">
                    <input type="checkbox" checked={!!p[k]} onChange={(e) => up(setPublications, i, { [k]: e.target.checked } as Partial<PublicationEntry>)} />
                    {k.replace('is_', '').toUpperCase()}
                  </label>
                ))}
              </div>
            </Field>
          </RowShell>
        ))}
      </Section>

      {/* Hợp đồng */}
      <Section icon={<FileSignature size={16} />} title="Hợp đồng NCKH / Dịch vụ" hint="Hợp đồng tư vấn, chuyển giao, dịch vụ KHCN" count={contracts.length}
        onAdd={() => setContracts((r) => [...r, { title: '' }])}>
        {contracts.map((c, i) => (
          <RowShell key={i} onRemove={() => rm(setContracts, i)}>
            <Field label="Tên hợp đồng" required className="md:col-span-2 lg:col-span-2">
              <Input value={c.title} onChange={(e) => up(setContracts, i, { title: e.target.value })} />
            </Field>
            <Field label="Loại"><Input value={c.contract_type ?? ''} onChange={(e) => up(setContracts, i, { contract_type: e.target.value || null })} placeholder="Tư vấn / Dịch vụ" /></Field>
            <Field label="Giá trị (VNĐ)"><Input value={c.value_amount ?? ''} onChange={(e) => up(setContracts, i, { value_amount: e.target.value || null })} placeholder="50000000" /></Field>
            <Field label="Đối tác" className="lg:col-span-2"><Input value={c.partner_org ?? ''} onChange={(e) => up(setContracts, i, { partner_org: e.target.value || null })} /></Field>
          </RowShell>
        ))}
      </Section>

      {/* Công tác khác */}
      <Section icon={<Landmark size={16} />} title="Công tác khác" hint="Công tác Đảng / Công đoàn / VILAS / khác" count={activities.length}
        onAdd={() => setActivities((r) => [...r, { kind: 'khac', content: '' }])}>
        {activities.map((a, i) => (
          <RowShell key={i} onRemove={() => rm(setActivities, i)}>
            <Field label="Nhóm">
              <Select value={a.kind} onChange={(e) => up(setActivities, i, { kind: e.target.value as OtherKind })}>
                {(Object.keys(OTHER_KIND_LABELS) as OtherKind[]).map((k) => <option key={k} value={k}>{OTHER_KIND_LABELS[k]}</option>)}
              </Select>
            </Field>
            <Field label="Nội dung" required className="md:col-span-2 lg:col-span-3">
              <Textarea rows={2} value={a.content} onChange={(e) => up(setActivities, i, { content: e.target.value })} />
            </Field>
          </RowShell>
        ))}
      </Section>

      {/* Thanh hành động dính đáy: dưới sm tràn hết bề ngang + chừa home indicator,
          nút chia đôi để dễ chạm. */}
      <div className="sticky bottom-0 z-20 -mx-3 flex flex-col gap-3 border-t border-hairline bg-surface/95 p-3 pb-safe shadow-sm backdrop-blur sm:mx-0 sm:flex-row sm:items-center sm:justify-between sm:rounded-xl sm:border sm:p-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-subink">Tổng cộng <strong className="text-ink">{total}</strong> dòng hoạt động</span>
          {savedAt ? (
            <span className="flex items-center gap-1.5 text-xs text-success"><Save size={12} /> Đã tự động lưu nháp lúc {formatDateTime(savedAt)}</span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-subink"><Save size={12} /> Nháp sẽ tự lưu khi bạn nhập</span>
          )}
        </div>
        <div className="flex gap-2 max-sm:[&>button]:flex-1">
          <Button variant="secondary" onClick={() => navigate('/activity-reports')}>Hủy</Button>
          <Button onClick={submit} loading={submitting} disabled={total === 0}>Nộp báo cáo</Button>
        </div>
      </div>
    </div>
  );
}
