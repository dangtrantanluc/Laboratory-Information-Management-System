/**
 * Báo cáo mẫu phân tích theo quý (m54).
 *
 * - Tài khoản lab (KTV, trưởng lab): thấy thẳng báo cáo của phòng mình trong quý đang chọn.
 * - Văn phòng / admin / Ban lãnh đạo: thấy bảng tình trạng nộp của mọi phòng; bấm một
 *   phòng để xem chi tiết (?dept=…). Văn phòng trả lại / chốt / xuất Excel.
 *
 * Trạng thái lọc nằm trên URL (?year=&quarter=&dept=) để thông báo và nút Back mở đúng chỗ;
 * thông báo chỉ mang id báo cáo (?report=…) nên trang tự đổi id đó ra quý + phòng.
 */
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ArrowLeft, TestTubes } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Field';
import { ErrorState, LoadingState } from '@/components/ui/States';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/lib/useAsync';
import { canViewAllQuarterlyReports } from '@/lib/rbac';
import * as api from '@/api/quarterlySampleReports';
import { QuarterlyOverview } from '@/components/quarterlySampleReports/QuarterlyOverview';
import { QuarterlyReportPanel } from '@/components/quarterlySampleReports/QuarterlyReportPanel';

export function QuarterlySampleReports() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const now = api.currentQuarter();
  const year = Number(params.get('year')) || now.year;
  const quarter = Number(params.get('quarter')) || now.quarter;
  const dept = params.get('dept') ?? undefined;
  const reportId = params.get('report');
  const viewAll = canViewAllQuarterlyReports(user);

  function update(next: Record<string, string | undefined>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined) p.delete(k);
      else p.set(k, v);
    }
    setParams(p);
  }

  // Mở từ thông báo: ?report=<id> → quý + phòng của báo cáo đó.
  useEffect(() => {
    if (!reportId) return;
    api
      .getReport(reportId)
      .then((r) =>
        setParams(
          { year: String(r.year), quarter: String(r.quarter), ...(viewAll ? { dept: r.department_id } : {}) },
          { replace: true },
        ),
      )
      .catch(() => update({ report: undefined }));
  }, [reportId]); // chỉ chạy khi id trong URL đổi

  const showPanel = !viewAll || !!dept;
  const { data, error, reload } = useAsync(
    () => (showPanel && !reportId ? api.getCurrent(year, quarter, dept) : Promise.resolve(null)),
    [showPanel, year, quarter, dept, reportId],
  );

  // Dữ liệu của quý / phòng KHÁC với lựa chọn hiện tại (vừa đổi bộ lọc, đang tải) thì không hiện.
  const stale =
    !data || data.year !== year || data.quarter !== quarter || (!!dept && data.department.id !== dept);

  const years = Array.from({ length: 4 }, (_, i) => now.year - i);
  const quarters = [1, 2, 3, 4].filter((q) => year < now.year || q <= now.quarter);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Báo cáo phân tích mẫu theo quý"
        description={
          viewAll
            ? 'Các phòng nghiên cứu nhập mẫu đã phân tích — Văn phòng kiểm tra, chốt và xuất Excel toàn Viện'
            : 'Nhập mẫu phòng đã phân tích trong quý, cuối quý nộp cho Văn phòng'
        }
        icon={<TestTubes size={20} />}
        actions={
          <div className="flex items-center gap-2">
            <Select
              aria-label="Quý"
              value={quarter}
              onChange={(e) => update({ quarter: e.target.value })}
              className="w-[110px]"
            >
              {quarters.map((q) => (
                <option key={q} value={q}>
                  Quý {api.ROMAN[q]}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Năm"
              value={year}
              onChange={(e) => {
                const y = Number(e.target.value);
                // Năm hiện tại chưa qua hết các quý — kéo quý về quý hiện tại nếu đang ở tương lai.
                update({
                  year: e.target.value,
                  ...(y === now.year && quarter > now.quarter ? { quarter: String(now.quarter) } : {}),
                });
              }}
              className="w-[110px]"
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
        }
      />

      {viewAll && dept && (
        <div>
          <Button variant="ghost" size="sm" onClick={() => update({ dept: undefined })}>
            <ArrowLeft size={14} /> Tất cả phòng — {api.periodLabel(year, quarter)}
          </Button>
        </div>
      )}

      {!showPanel ? (
        <QuarterlyOverview year={year} quarter={quarter} onOpen={(id) => update({ dept: id })} />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : data && !stale ? (
        // Tải lại sau khi lưu một dòng thì giữ bảng cũ trên màn hình — tránh chớp.
        <QuarterlyReportPanel current={data} onChanged={reload} />
      ) : (
        <LoadingState />
      )}
    </div>
  );
}
