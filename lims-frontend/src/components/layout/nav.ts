import {
  LayoutDashboard,
  ClipboardList,
  FlaskConical,
  Wrench,
  Users,
  Building2,
  UserSquare2,
  Bell,
  ScrollText,
  Settings,
  IdCard,
  FolderKanban,
  BookText,
  UserCog,
  ClipboardCheck,
  Presentation,
  HeartHandshake,
  BarChart3,
  FileText,
  type LucideIcon,
} from 'lucide-react';
import type { CurrentUser } from '@/types';
import {
  canViewSamples,
  canViewChemicals,
  canManageUsers,
  canViewAudit,
  canViewCustomers,
  canListHr,
  canViewResearch,
  canViewDocuments,
  canApproveDocuments,
  canViewDocumentStats,
  canViewEquipment,
  canViewReports,
} from '@/lib/rbac';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  group: 'main' | 'document' | 'hr' | 'research' | 'catalog' | 'system';
  /** Hàm kiểm tra hiển thị theo quyền. Bỏ trống = mọi user đã đăng nhập. */
  visible?: (user: CurrentUser | null) => boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Tổng quan', icon: LayoutDashboard, group: 'main' },
  { to: '/samples', label: 'Mẫu thử nghiệm', icon: ClipboardList, group: 'main', visible: canViewSamples },
  { to: '/chemicals', label: 'Hóa chất', icon: FlaskConical, group: 'main', visible: canViewChemicals },
  { to: '/equipment', label: 'Thiết bị', icon: Wrench, group: 'main', visible: canViewEquipment },
  { to: '/reports', label: 'Báo cáo', icon: BarChart3, group: 'main', visible: canViewReports },

  // ── M3: Quản lý tài liệu ──
  { to: '/documents', label: 'Tài liệu', icon: FileText, group: 'document', visible: canViewDocuments },
  { to: '/documents/pending', label: 'Chờ duyệt', icon: ClipboardCheck, group: 'document', visible: canApproveDocuments },
  { to: '/documents/stats', label: 'Thống kê truy cập', icon: BarChart3, group: 'document', visible: canViewDocumentStats },

  // ── M4: Nhân sự ──
  { to: '/hr', label: 'Hồ sơ nhân sự', icon: IdCard, group: 'hr', visible: canListHr },
  { to: '/my-profile', label: 'Hồ sơ của tôi', icon: UserSquare2, group: 'hr' },

  // ── M4: NCKH (ẩn với accountant) ──
  { to: '/research/projects', label: 'Đề tài NCKH', icon: FolderKanban, group: 'research', visible: canViewResearch },
  { to: '/research/publications', label: 'Bài báo & Sáng chế', icon: BookText, group: 'research', visible: canViewResearch },
  { to: '/research/mentorships', label: 'Hướng dẫn SV', icon: UserCog, group: 'research', visible: canViewResearch },
  { to: '/research/lab-registrations', label: 'Đăng ký lab', icon: ClipboardCheck, group: 'research', visible: canViewResearch },
  { to: '/research/teaching', label: 'Môn giảng dạy', icon: Presentation, group: 'research', visible: canViewResearch },
  { to: '/research/community', label: 'Phục vụ cộng đồng', icon: HeartHandshake, group: 'research', visible: canViewResearch },
  { to: '/research/stats', label: 'Thống kê thành tích', icon: BarChart3, group: 'research', visible: canViewResearch },

  { to: '/customers', label: 'Khách hàng', icon: UserSquare2, group: 'catalog', visible: canViewCustomers },
  { to: '/users', label: 'Tài khoản', icon: Users, group: 'catalog', visible: canManageUsers },
  { to: '/departments', label: 'Phòng ban', icon: Building2, group: 'catalog', visible: canManageUsers },
  { to: '/notifications', label: 'Thông báo', icon: Bell, group: 'system' },
  { to: '/audit', label: 'Nhật ký hệ thống', icon: ScrollText, group: 'system', visible: canViewAudit },
  { to: '/settings', label: 'Cài đặt & Tài khoản', icon: Settings, group: 'system' },
];

export const GROUP_LABELS: Record<NavItem['group'], string> = {
  main: 'Nghiệp vụ',
  document: 'Tài liệu',
  hr: 'Nhân sự',
  research: 'NCKH',
  catalog: 'Danh mục',
  system: 'Hệ thống',
};

export function visibleNav(user: CurrentUser | null): NavItem[] {
  return NAV_ITEMS.filter((i) => !i.visible || i.visible(user));
}
