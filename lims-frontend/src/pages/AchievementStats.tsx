import { useState } from 'react';
import { BarChart3, FileSpreadsheet, Search } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Field, Select, Input } from '@/components/ui/Field';
import { LoadingState, EmptyState } from '@/components/ui/States';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { describeError } from '@/lib/errors';
import type { AchievementStats as Stats } from '@/types';
import * as researchApi from '@/api/research';
import type { StatsFilters } from '@/api/research';
import * as usersApi from '@/api/users';

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <CardBody className="pt-5">
        <p className="text-xs text-subink">{label}</p>
        <p className="text-2xl font-bold text-ink">{value}</p>
      </CardBody>
    </Card>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, number>; }) {
  const entries = Object.entries(data ?? {});
  if (entries.length === 0) return null;
  return (
    <Card>
      <CardHeader title={title} />
      <CardBody className="divide-y divide-hairline pt-0">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between py-2 text-sm">
            <span className="text-subink">{k}</span>
            <span className="font-semibold text-ink">{v}</span>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

export function AchievementStats() {
  const { user } = useAuth();
  const toast = useToast();
  const isStaff = user?.role === 'staff';

  const [groupBy, setGroupBy] = useState<'individual' | 'department'>(isStaff ? 'individual' : 'department');
  const [userId, setUserId] = useState(isStaff ? user?.id ?? '' : '');
  const [departmentId, setDepartmentId] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [applied, setApplied] = useState<StatsFilters | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data: users } = useAsync(() => usersApi.listUsers({ limit: 100 }), []);
  const { data: depts } = useAsync(() => usersApi.listDepartments(), []);

  const statsQ = useAsync<Stats | null>(
    () => (applied ? researchApi.getAchievementStats(applied) : Promise.resolve(null)),
    [applied],
  );

  function buildFilters(): StatsFilters | null {
    if (from && to && from > to) {
      toast.error('Từ ngày phải trước đến ngày');
      return null;
    }
    return {
      group_by: groupBy,
      user_id: groupBy === 'individual' ? userId || undefined : undefined,
      department_id: groupBy === 'department' ? departmentId || undefined : undefined,
      from: from || undefined,
      to: to || undefined,
    };
  }

  function run() {
    const f = buildFilters();
    if (f) setApplied(f);
  }

  async function exportXlsx() {
    const f = buildFilters();
    if (!f) return;
    setExporting(true);
    try {
      await researchApi.exportAchievementStatsXlsx(f);
      toast.success('Đã tải file Excel');
    } catch (err) {
      toast.error(describeError(err).title);
    } finally {
      setExporting(false);
    }
  }

  const stats = statsQ.data;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Thống kê thành tích"
        description="Tổng hợp thành tích NCKH theo cá nhân / phòng ban / thời gian"
        icon={<BarChart3 size={20} />}
        actions={
          <Button variant="secondary" onClick={exportXlsx} loading={exporting}>
            <FileSpreadsheet size={16} /> Xuất Excel
          </Button>
        }
      />

      <Card>
        <CardBody className="pt-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Tổng hợp theo">
              <Select
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value as 'individual' | 'department')}
                disabled={isStaff}
              >
                <option value="individual">Cá nhân</option>
                <option value="department">Phòng ban</option>
              </Select>
            </Field>
            {groupBy === 'individual' ? (
              <Field label="Cá nhân">
                <Select value={userId} onChange={(e) => setUserId(e.target.value)} disabled={isStaff}>
                  <option value="">— Chọn —</option>
                  {(users?.data ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field label="Phòng ban">
                <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                  <option value="">— Toàn hệ thống —</option>
                  {(depts?.data ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Từ ngày">
              <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="Đến ngày">
              <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </Field>
            <div className="flex items-end">
              <Button onClick={run} className="w-full">
                <Search size={16} /> Xem thống kê
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {statsQ.loading ? (
        <LoadingState />
      ) : !stats ? (
        <Card>
          <EmptyState
            title="Chọn tiêu chí và bấm Xem thống kê"
            description="Kết quả tổng hợp sẽ hiển thị tại đây."
          />
        </Card>
      ) : (
        <>
          <div className="text-sm text-subink">
            {stats.group_by === 'department'
              ? `Phòng: ${stats.department_name ?? 'Toàn hệ thống'}`
              : `Cá nhân: ${stats.user_name ?? '—'}`}
            {stats.period?.from && ` · từ ${stats.period.from}`}
            {stats.period?.to && ` đến ${stats.period.to}`}
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <StatCard label="Đề tài" value={stats.projects?.total ?? 0} />
            <StatCard label="Bài báo" value={stats.publications?.total ?? 0} />
            <StatCard label="Sáng chế / GPHI" value={stats.patents ?? 0} />
            <StatCard label="Hướng dẫn SV" value={stats.mentorships ?? 0} />
            <StatCard label="Đăng ký lab (đã duyệt)" value={stats.lab_registrations_approved ?? 0} />
            <StatCard label="Môn giảng dạy" value={stats.teaching_courses ?? 0} />
            <StatCard label="Phục vụ cộng đồng" value={stats.community_services ?? 0} />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Breakdown title="Đề tài theo cấp" data={stats.projects?.by_level ?? {}} />
            <Breakdown title="Bài báo theo chỉ số" data={stats.publications?.by_index ?? {}} />
          </div>
        </>
      )}
    </div>
  );
}
