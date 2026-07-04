import type { CurrentUser, Permission, Role } from '@/types';

/**
 * RBAC client-side — đọc ma trận quyền từ /auth/me (permissions: {resource, action}).
 * Dùng để ẩn/hiện menu + nút. Backend luôn re-validate (NFR-SEC).
 *
 * Lưu ý: quyền trưởng nhóm (assign/approve/finalize) phái sinh từ is_dept_lead.
 * Backend đã đưa sample:assign / sample:approve vào permissions của admin/leader,
 * nhưng với staff chỉ có khi is_dept_lead=true → ta kết hợp cả hai nguồn.
 */

export function hasPermission(user: CurrentUser | null, resource: string, action: string): boolean {
  if (!user) return false;
  return user.permissions.some((p: Permission) => p.resource === resource && p.action === action);
}

/** Kế toán bị chặn toàn bộ nghiệp vụ mẫu. */
export function isAccountant(user: CurrentUser | null): boolean {
  return user?.role === 'accountant';
}

/** Có quyền xem field giá hóa chất (cost). */
export function canViewCost(user: CurrentUser | null): boolean {
  return hasPermission(user, 'chemical', 'cost') || user?.role === 'admin' || user?.role === 'leader';
}

/** Quyền trưởng nhóm phòng: phân công / duyệt / chốt mẫu. */
export function canLeadSample(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  return user.role === 'staff' && user.is_dept_lead;
}

// ── Helpers theo nghiệp vụ (tổng hợp) ──────────────────────────
export function canViewSamples(user: CurrentUser | null): boolean {
  return !!user && !isAccountant(user);
}
export function canCreateSample(user: CurrentUser | null): boolean {
  return hasPermission(user, 'sample', 'create');
}
export function canEnterResult(user: CurrentUser | null): boolean {
  return hasPermission(user, 'sample', 'result') || user?.role === 'admin';
}
export function canAssignSample(user: CurrentUser | null): boolean {
  return canLeadSample(user);
}
export function canApproveResult(user: CurrentUser | null): boolean {
  return canLeadSample(user);
}

export function canViewChemicals(user: CurrentUser | null): boolean {
  return hasPermission(user, 'chemical', 'read') || !!user;
}
export function canTransactChemical(user: CurrentUser | null): boolean {
  return hasPermission(user, 'chemical', 'transact') || user?.role === 'admin';
}
export function canManageChemical(user: CurrentUser | null): boolean {
  return hasPermission(user, 'chemical', 'create') || user?.role === 'admin';
}

export function canManageUsers(user: CurrentUser | null): boolean {
  return hasPermission(user, 'user', 'manage');
}
export function canViewAudit(user: CurrentUser | null): boolean {
  return hasPermission(user, 'audit', 'read');
}
export function canManageCustomers(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'staff';
}
export function canViewCustomers(user: CurrentUser | null): boolean {
  return !!user && !isAccountant(user);
}

// ── M4: Nhân sự (HR) ────────────────────────────────────────────
/** Thấy menu "Nhân sự" (danh sách hồ sơ): admin/leader/accountant. Staff chỉ "Hồ sơ của tôi". */
export function canListHr(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader' || user?.role === 'accountant';
}
/** Tạo/sửa hồ sơ + hợp đồng: admin/accountant. */
export function canManageHr(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'accountant';
}
/** Ghi nâng lương / sửa lương: chỉ admin/accountant (leader chỉ xem). */
export function canEditSalary(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'accountant';
}
/** Quản lý hồ sơ năng lực (bằng/chứng chỉ/ủy quyền): admin/leader. */
export function canManageCompetence(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}
/** Xem hồ sơ năng lực: admin/leader (+ chính chủ qua trang Hồ sơ của tôi). */
export function canViewCompetence(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

// ── M4: NCKH (Nghiên cứu khoa học) ──────────────────────────────
/** Menu NCKH: admin/leader/staff thấy; accountant KHÔNG thấy (403). */
export function canViewResearch(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'accountant';
}
/** Quản lý thành tích NCKH (CRUD): admin/leader/staff (staff scope own — BE enforce). */
export function canManageResearch(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'accountant';
}

// ── M3: Quản lý tài liệu (Document Control) ─────────────────────
/** Menu "Tài liệu": mọi vai trò đã đăng nhập (kể cả accountant — chỉ xem approved). */
export function canViewDocuments(user: CurrentUser | null): boolean {
  return !!user;
}
/** Tạo/sửa tài liệu & version (ghi): admin/leader/staff. Accountant CHỈ xem → false. */
export function canManageDocuments(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'accountant';
}
/** Duyệt/từ chối/ban hành: admin/leader hoặc trưởng nhóm phòng (is_dept_lead). Accountant → false. */
export function canApproveDocuments(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  return user.role === 'staff' && user.is_dept_lead;
}
/** Xem thống kê truy cập tài liệu (R15): admin/leader/staff (staff scope own — BE enforce). */
export function canViewDocumentStats(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'accountant';
}
/** Xuất Excel thống kê truy cập: admin/leader. */
export function canExportDocumentStats(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

// ── M5: Thiết bị & Hiệu chuẩn (Equipment & Calibration) ─────────
/** Menu "Thiết bị": mọi vai trò đã đăng nhập (kể cả accountant — chỉ xem). */
export function canViewEquipment(user: CurrentUser | null): boolean {
  return !!user;
}
/**
 * Quyền GHI thiết bị/hiệu chuẩn (tạo/sửa/đính kèm/ghi hiệu chuẩn).
 * KHÁC M3: leader CHỈ XEM (không ghi). accountant CHỈ XEM.
 * staff ghi được nhưng CHỈ phòng mình → cần kiểm thêm phòng qua canWriteEquipmentDept().
 * admin: full.
 */
export function canWriteEquipment(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'staff';
}
/**
 * Quyền ghi cho 1 thiết bị cụ thể theo phòng ban.
 * admin: mọi phòng. staff: chỉ phòng mình (departmentId của thiết bị = phòng user).
 * leader/accountant: không bao giờ.
 * @param equipmentDeptId phòng sở hữu thiết bị (null khi tạo mới → so theo phòng user).
 */
export function canWriteEquipmentDept(
  user: CurrentUser | null,
  equipmentDeptId: string | null | undefined,
): boolean {
  if (!user) return false;
  if (user.role === 'admin') return true;
  if (user.role !== 'staff') return false;
  if (!equipmentDeptId) return !!user.department; // tạo mới — staff phải có phòng
  return user.department?.id === equipmentDeptId;
}
/** Chạy CRON nhắc hiệu chuẩn thủ công: chỉ admin. */
export function canRunCalibrationCron(user: CurrentUser | null): boolean {
  return user?.role === 'admin';
}

// ── M6: Báo cáo & Dashboard ─────────────────────────────────────
/** Menu "Báo cáo": mọi vai trò thấy (accountant chỉ phần hóa chất). */
export function canViewReports(user: CurrentUser | null): boolean {
  return !!user;
}
/** Báo cáo mẫu (#3): ẩn với accountant (B03). */
export function canViewSampleReport(user: CurrentUser | null): boolean {
  return !!user && !isAccountant(user);
}
/** Báo cáo hóa chất (#4): mọi vai trò (field tiền theo canViewCost). */
export function canViewChemicalReport(user: CurrentUser | null): boolean {
  return !!user;
}
/** Thống kê truy cập hệ thống R15 (#10/#11): CHỈ admin/leader (audit:read). */
export function canViewSystemAccess(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

export const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'admin', label: 'Quản trị viên' },
  { value: 'leader', label: 'Ban lãnh đạo' },
  { value: 'accountant', label: 'Kế toán' },
  { value: 'staff', label: 'Nhân sự / KTV' },
];
