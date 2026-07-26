import type { CurrentUser, Role } from '@/types';
import type { LucideIcon } from 'lucide-react';
import {
  Award,
  BarChart3,
  BookText,
  Building2,
  ClipboardCheck,
  ClipboardList,
  CreditCard,
  FileSignature,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  FolderKanban,
  HeartHandshake,
  Inbox,
  LayoutDashboard,
  Landmark,
  ListChecks,
  Presentation,
  Receipt,
  ScrollText,
  TrendingUp,
  UserCog,
  UserSquare2,
  Users,
  Wrench,
} from 'lucide-react';

/**
 * Kiến trúc thông tin điều hướng (IA) — nhóm theo CÔNG VIỆC (job-to-be-done),
 * không theo module kỹ thuật. Menu giờ có icon để dễ nhận diện.
 */

/** Nguồn badge (số đếm động) gắn trên item — số thật lấy qua useNavBadges(). */
export type BadgeKey = 'approvals';

export interface NavLeaf {
  to: string;
  label: string;
  icon?: LucideIcon;
  /** Bỏ trống = mọi user đã đăng nhập. */
  roles?: Role[];
  badge?: BadgeKey;
}
export interface NavSubGroup {
  label: string;
  items: NavLeaf[];
}
export interface NavGroup {
  id: string;
  label: string;
  /** Mở sẵn lúc đầu (nhóm dùng hằng ngày). Mặc định đóng để giảm cuộn. */
  defaultOpen?: boolean;
  items?: NavLeaf[];
  /** Nhóm con (chỉ dùng cho domain lớn: Nghiên cứu & Đào tạo). */
  subgroups?: NavSubGroup[];
}

// ── Nhóm vai trò dùng lại ────────────────────────────────────────
const LAB: Role[] = ['lab_manager', 'staff'];
const LAB_LEAD: Role[] = ['admin', 'leader', 'lab_manager', 'staff'];
const APPROVERS: Role[] = ['admin', 'leader', 'qms', 'lab_manager'];
const NCKH_LEAD: Role[] = ['admin', 'leader', 'lab_manager']; // giảng dạy/hướng dẫn — không cho KTV
const RESEARCH_VIEW: Role[] = [...LAB_LEAD, 'office']; // NCKH: văn phòng XEM read-only
const REPORTERS: Role[] = ['admin', 'leader', 'lab_manager', 'staff', 'office']; // báo cáo hoạt động

/** Item đứng riêng trên cùng — không thuộc nhóm nào. */
export const DASHBOARD: NavLeaf = { to: '/dashboard', label: 'Tổng quan', icon: LayoutDashboard };

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'workspace',
    label: 'Không gian của tôi',
    defaultOpen: true,
    items: [
      { to: '/activity-reports', label: 'Báo cáo hoạt động', icon: ClipboardList, roles: REPORTERS },
    ],
  },
  {
    id: 'operations',
    label: 'Vận hành thử nghiệm',
    defaultOpen: true,
    items: [
      { to: '/sample-flow', label: 'Nhận & Chuyển mẫu', icon: Inbox, roles: ['admin', 'leader', 'reception', ...LAB] },
      { to: '/samples', label: 'Mẫu thử nghiệm', icon: FlaskConical, roles: LAB_LEAD },
      { to: '/chemicals', label: 'Hóa chất', icon: FlaskConical, roles: [...LAB_LEAD, 'office'] },
      { to: '/equipment', label: 'Thiết bị & Hiệu chuẩn', icon: Wrench, roles: ['admin', 'leader', 'lab_manager', 'office'] },
      { to: '/test-parameters', label: 'Chỉ tiêu thử nghiệm', icon: ListChecks },
      { to: '/quotations', label: 'Báo giá', icon: Receipt, roles: ['admin', 'leader', 'reception', 'office'] },
    ],
  },
  {
    id: 'quality',
    label: 'Chất lượng & Tài liệu',
    items: [
      { to: '/documents', label: 'Tài liệu', icon: FileText },
      { to: '/documents/pending', label: 'Chờ duyệt', icon: ClipboardCheck, roles: APPROVERS, badge: 'approvals' },
      { to: '/forms', label: 'Kho biểu mẫu VILAS', icon: FileSpreadsheet, roles: ['admin', 'leader', 'reception', 'qms', ...LAB] },
    ],
  },
  {
    id: 'research',
    label: 'Nghiên cứu & Đào tạo',
    subgroups: [
      {
        label: 'Nghiên cứu',
        items: [
          { to: '/research/projects', label: 'Đề tài NCKH', icon: FolderKanban, roles: RESEARCH_VIEW },
          { to: '/research/publications', label: 'Bài báo & Sáng chế', icon: BookText, roles: RESEARCH_VIEW },
          { to: '/research/contracts', label: 'Hợp đồng NCKH', icon: FileSignature, roles: ['admin', 'leader', 'office'] },
          { to: '/research/community', label: 'Phục vụ cộng đồng', icon: HeartHandshake, roles: RESEARCH_VIEW },
        ],
      },
      {
        label: 'Giảng dạy & Hướng dẫn',
        items: [
          { to: '/research/teaching', label: 'Môn giảng dạy', icon: Presentation, roles: [...NCKH_LEAD, 'office'] },
          { to: '/research/mentorships', label: 'Hướng dẫn SV', icon: UserCog, roles: [...NCKH_LEAD, 'office'] },
          { to: '/research/certificates', label: 'Chứng nhận đào tạo', icon: Award, roles: RESEARCH_VIEW },
        ],
      },
    ],
  },
  {
    id: 'people',
    label: 'Nhân sự & Hành chính',
    items: [
      { to: '/hr', label: 'Hồ sơ nhân sự', icon: Users, roles: ['admin', 'leader', 'office'] },
      { to: '/staff-activities', label: 'Công tác khác', icon: Landmark },
      { to: '/lab-access-cards', label: 'Thẻ vào PTN', icon: CreditCard, roles: ['admin', 'leader', 'qms', 'office'] },
    ],
  },
  {
    id: 'analytics',
    label: 'Báo cáo & Phân tích',
    items: [
      { to: '/reports', label: 'Báo cáo tổng hợp', icon: BarChart3, roles: ['admin', 'leader', 'reception', 'qms', 'lab_manager', 'office'] },
      { to: '/research/stats', label: 'Thống kê thành tích', icon: TrendingUp, roles: RESEARCH_VIEW },
      { to: '/documents/stats', label: 'Thống kê truy cập TL', icon: BarChart3, roles: ['admin'] },
    ],
  },
  {
    id: 'admin',
    label: 'Quản trị',
    items: [
      { to: '/users', label: 'Tài khoản', icon: Users, roles: ['admin'] },
      { to: '/departments', label: 'Phòng ban', icon: Building2, roles: ['admin'] },
      { to: '/customers', label: 'Khách hàng', icon: UserSquare2, roles: ['admin', 'leader', 'reception'] },
      { to: '/audit', label: 'Nhật ký hệ thống', icon: ScrollText, roles: ['admin', 'leader'] },
    ],
  },
];

// ── Helpers lọc theo vai trò ─────────────────────────────────────
function canSee(user: CurrentUser | null, roles?: Role[]): boolean {
  return !roles || (!!user && roles.includes(user.role));
}

/** Item con hiển thị cho user (đã lọc vai trò). */
export function visibleLeaves(user: CurrentUser | null, items?: NavLeaf[]): NavLeaf[] {
  return (items ?? []).filter((i) => canSee(user, i.roles));
}

/** Nhóm còn item hợp lệ sau khi lọc vai trò (nhóm rỗng bị loại bỏ, không render khung). */
export interface ResolvedGroup {
  id: string;
  label: string;
  defaultOpen?: boolean;
  items: NavLeaf[];
  subgroups: NavSubGroup[];
}
export function visibleGroups(user: CurrentUser | null): ResolvedGroup[] {
  const out: ResolvedGroup[] = [];
  for (const g of NAV_GROUPS) {
    const items = visibleLeaves(user, g.items);
    const subgroups = (g.subgroups ?? [])
      .map((sg) => ({ label: sg.label, items: visibleLeaves(user, sg.items) }))
      .filter((sg) => sg.items.length > 0);
    if (items.length === 0 && subgroups.length === 0) continue;
    out.push({ id: g.id, label: g.label, defaultOpen: g.defaultOpen, items, subgroups });
  }
  return out;
}

/** Danh sách phẳng mọi item user thấy — dùng cho ô tìm kiếm + favorites/recent. */
export function flatLeaves(user: CurrentUser | null): NavLeaf[] {
  const all: NavLeaf[] = [DASHBOARD];
  for (const g of visibleGroups(user)) {
    all.push(...g.items);
    for (const sg of g.subgroups) all.push(...sg.items);
  }
  return all;
}
