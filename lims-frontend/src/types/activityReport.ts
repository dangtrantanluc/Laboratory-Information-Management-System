/**
 * Kiểu dữ liệu Báo cáo hoạt động hàng tháng (m25) — tách khỏi types/index.ts.
 *
 * Đây là domain riêng: một gói báo cáo của một người trong một kỳ, bên trong nhúng
 * BẢN TÓM TẮT của các bản ghi thành tích (đề tài, công bố, hợp đồng, giảng dạy,
 * công tác khác) chứ không phải bản đầy đủ — nên không gộp vào ./research.
 *
 * Các trường phân loại dùng đúng union của ./research thay vì `string`: bảng nhãn
 * là Record<Union, string>, khai `string` thì tra nhãn mất type-safe và mã thô lọt
 * ra giao diện (đã xảy ra thật ở ActivityReports).
 *
 * index.ts re-export toàn bộ nên mọi `from '@/types'` sẵn có giữ nguyên.
 */
import type { PublicationType, PubScope, StaffActivityKind } from './research';

// ── Báo cáo hoạt động hàng tháng (m25) ───────────────────────────
export type ActivityReportStatus = 'draft' | 'submitted' | 'reviewed';

export const ACTIVITY_REPORT_STATUS_LABELS: Record<ActivityReportStatus, string> = {
  draft: 'Nháp',
  submitted: 'Đã nộp',
  reviewed: 'Đã tổng hợp',
};

export interface ActivityReportCounts {
  teaching: number;
  projects: number;
  publications: number;
  contracts: number;
  activities: number;
}

export interface ActivityReport {
  id: string;
  reporter_user_id: string;
  reporter_name: string | null;
  department_id: string | null;
  department_name: string | null;
  period_label: string;
  period_year: number | null;
  academic_year: string | null;
  status: ActivityReportStatus;
  note: string | null;
  submitted_at: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
  counts?: ActivityReportCounts;
  // chi tiết (khi GET /{id})
  teaching?: Array<{
    id: string;
    course_name: string;
    hk1_theory_hours: number | null;
    hk1_practice_hours: number | null;
    hk2_theory_hours: number | null;
    hk2_practice_hours: number | null;
    hk3_theory_hours: number | null;
    hk3_practice_hours: number | null;
  }>;
  projects?: Array<{ id: string; title: string; level: string | null; status: string; budget_amount: string | null }>;
  publications?: Array<{
    id: string;
    title: string;
    // Union chứ không phải string: các bảng nhãn (PUBLICATION_TYPE_LABELS…) là
    // Record<Union,string>, khai string thì tra nhãn không type-safe và dễ lọt mã
    // thô ra giao diện — đúng lỗi đã xảy ra ở ActivityReports.
    type: PublicationType;
    pub_scope: PubScope | null;
    journal: string | null;
    year: number | null;
    is_scie: boolean;
    is_scopus: boolean;
  }>;
  contracts?: Array<{ id: string; title: string; contract_type: string | null; value_amount: string | null }>;
  activities?: Array<{ id: string; kind: StaffActivityKind; content: string }>;
}
