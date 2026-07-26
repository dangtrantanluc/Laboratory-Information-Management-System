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

/** Văn phòng bị chặn toàn bộ nghiệp vụ mẫu. */
export function isOffice(user: CurrentUser | null): boolean {
  return user?.role === 'office';
}

/** Có quyền xem field giá hóa chất (cost). */
export function canViewCost(user: CurrentUser | null): boolean {
  return hasPermission(user, 'chemical', 'cost') || user?.role === 'admin' || user?.role === 'leader';
}

/** Quyền trưởng nhóm phòng: phân công / duyệt / chốt mẫu. */
export function canLeadSample(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  // Trưởng phòng lab luôn có quyền lead; KTV chỉ khi được gán làm trưởng nhóm.
  if (user.role === 'lab_manager') return true;
  return user.role === 'staff' && user.is_dept_lead;
}

// ── Helpers theo nghiệp vụ (tổng hợp) ──────────────────────────
export function canViewSamples(user: CurrentUser | null): boolean {
  return !!user && !isOffice(user);
}
export function canCreateSample(user: CurrentUser | null): boolean {
  return hasPermission(user, 'sample', 'create');
}
export function canEnterResult(user: CurrentUser | null): boolean {
  return hasPermission(user, 'sample', 'result') || user?.role === 'admin';
}
export function canAssignSample(user: CurrentUser | null): boolean {
  // Phòng nhận mẫu điều phối mẫu → phòng lab (sample:assign toàn hệ thống).
  return canLeadSample(user) || hasPermission(user, 'sample', 'assign');
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
  // Khách hàng thuộc nghiệp vụ Phòng nhận mẫu (GĐ2).
  return user?.role === 'admin' || user?.role === 'staff' || user?.role === 'reception';
}
export function canViewCustomers(user: CurrentUser | null): boolean {
  return !!user && !isOffice(user);
}

// ── M4: Nhân sự (HR) ────────────────────────────────────────────
/** Thấy menu "Nhân sự" (danh sách hồ sơ): admin/leader/office. Staff chỉ xem hồ sơ của mình trong trang "Hồ sơ cá nhân". */
export function canListHr(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader' || user?.role === 'office';
}
/** Tạo/sửa hồ sơ + hợp đồng: admin/office. */
export function canManageHr(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'office';
}
/** Ghi nâng lương / sửa lương: chỉ admin/office (leader chỉ xem). */
export function canEditSalary(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'office';
}
/** Quản lý hồ sơ năng lực (bằng/chứng chỉ/ủy quyền): admin/leader. */
export function canManageCompetence(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}
/** Xem hồ sơ năng lực: admin/leader (+ chính chủ qua trang Hồ sơ cá nhân). */
export function canViewCompetence(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

// ── M4: NCKH (Nghiên cứu khoa học) ──────────────────────────────
/** Menu NCKH — XEM: mọi vai trò đã đăng nhập, KỂ CẢ VĂN PHÒNG (read-only toàn bộ NCKH). */
export function canViewResearch(user: CurrentUser | null): boolean {
  return !!user;
}
/** Quản lý thành tích NCKH (CRUD): admin/leader/staff. Office CHỈ xem → false. */
export function canManageResearch(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'office';
}

// ── 3 menu hành chính m23 (Hợp đồng / Công tác khác / Chứng nhận đào tạo) ──
/** Văn phòng LÀ người quản lý 3 menu này (đọc + ghi), cùng admin/leader. */
export function canManageActivities(user: CurrentUser | null): boolean {
  return !!user && ['admin', 'leader', 'office'].includes(user.role);
}
/** Xem menu hành chính: nhóm quản lý + khối lab (staff/lab_manager). */
export function canViewActivities(user: CurrentUser | null): boolean {
  return !!user && ['admin', 'leader', 'lab_manager', 'staff', 'office'].includes(user.role);
}

/**
 * Hướng dẫn SV & Môn giảng dạy: việc của giảng viên/phụ trách khoa học (admin/leader/lab_manager),
 * KHÔNG phải việc của KTV vận hành thử nghiệm → staff không thấy menu. Văn phòng ĐƯỢC xem (read-only).
 */
export function canViewMentorship(user: CurrentUser | null): boolean {
  return ['admin', 'leader', 'lab_manager', 'office'].includes(user?.role ?? '');
}
export function canViewTeaching(user: CurrentUser | null): boolean {
  return ['admin', 'leader', 'lab_manager', 'office'].includes(user?.role ?? '');
}
/** Quản lý (CRUD) Hướng dẫn SV & Giảng dạy: admin/leader/lab_manager (office CHỈ xem). */
export function canManageMentorshipTeaching(user: CurrentUser | null): boolean {
  return ['admin', 'leader', 'lab_manager'].includes(user?.role ?? '');
}

// ── M3: Quản lý tài liệu (Document Control) ─────────────────────
/** Menu "Tài liệu": mọi vai trò đã đăng nhập (kể cả office — chỉ xem approved). */
export function canViewDocuments(user: CurrentUser | null): boolean {
  return !!user;
}
/** Tạo/sửa tài liệu & version (ghi): admin/leader/staff. Office CHỈ xem → false. */
export function canManageDocuments(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'office';
}
/** Duyệt/từ chối/ban hành: admin/leader hoặc trưởng nhóm phòng (is_dept_lead). Office → false. */
export function canApproveDocuments(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  // QLCL kiểm soát tài liệu toàn hệ thống; trưởng phòng lab duyệt trong phòng.
  if (user.role === 'qms') return true;
  if (user.role === 'lab_manager') return true;
  return user.role === 'staff' && user.is_dept_lead;
}
/** Xem thống kê truy cập tài liệu (R15): admin/leader/staff (staff scope own — BE enforce). */
export function canViewDocumentStats(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'office';
}
/** Xuất Excel thống kê truy cập: admin/leader. */
export function canExportDocumentStats(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

// ── M5: Thiết bị & Hiệu chuẩn (Equipment & Calibration) ─────────
/** Menu "Thiết bị": admin/leader/lab_manager/office (chỉ xem). KTV không cần dùng module này. */
export function canViewEquipment(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'staff';
}
/**
 * Quyền GHI thiết bị/hiệu chuẩn (tạo/sửa/đính kèm/ghi hiệu chuẩn).
 * KHÁC M3: leader CHỈ XEM (không ghi). office CHỈ XEM.
 * admin: full. lab_manager: CHỈ phòng mình → cần kiểm thêm phòng qua canWriteEquipmentDept().
 */
export function canWriteEquipment(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'lab_manager';
}
/**
 * Quyền ghi cho 1 thiết bị cụ thể theo phòng ban.
 * admin: mọi phòng. lab_manager: chỉ phòng mình (departmentId của thiết bị = phòng user).
 * leader/office: không bao giờ.
 * @param equipmentDeptId phòng sở hữu thiết bị (null khi tạo mới → so theo phòng user).
 */
export function canWriteEquipmentDept(
  user: CurrentUser | null,
  equipmentDeptId: string | null | undefined,
): boolean {
  if (!user) return false;
  if (user.role === 'admin') return true;
  if (user.role !== 'lab_manager') return false;
  if (!equipmentDeptId) return !!user.department; // tạo mới — phải có phòng
  return user.department?.id === equipmentDeptId;
}
/** Chạy CRON nhắc hiệu chuẩn thủ công: chỉ admin. */
export function canRunCalibrationCron(user: CurrentUser | null): boolean {
  return user?.role === 'admin';
}

// ── M6: Báo cáo & Dashboard ─────────────────────────────────────
/** Menu "Báo cáo": mọi vai trò thấy trừ KTV (không cần dùng module báo cáo/thống kê). */
export function canViewReports(user: CurrentUser | null): boolean {
  return !!user && user.role !== 'staff';
}
/** Báo cáo mẫu (#3): ẩn với office (B03). */
export function canViewSampleReport(user: CurrentUser | null): boolean {
  return !!user && !isOffice(user);
}
/** Báo cáo hóa chất (#4): mọi vai trò (field tiền theo canViewCost). */
export function canViewChemicalReport(user: CurrentUser | null): boolean {
  return !!user;
}
/** Thống kê truy cập hệ thống R15 (#10/#11): CHỈ admin/leader (audit:read). */
export function canViewSystemAccess(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader';
}

// ── M8: NC & CAPA (EPIC-QMS §7.10/§8.7) ─────────────────────────
/** Menu "Không phù hợp / CAPA": admin/leader/staff. Office KHÔNG (cách ly lab). */
export function canViewNC(user: CurrentUser | null): boolean {
  return hasPermission(user, 'nonconformity', 'read') || (!!user && !isOffice(user));
}
/** Tạo phiếu NC: admin/leader/staff (staff scope phòng — BE enforce). */
export function canCreateNC(user: CurrentUser | null): boolean {
  return hasPermission(user, 'nonconformity', 'create') || user?.role === 'admin';
}
/**
 * Quản lý CAPA (mở/đóng CAPA, thêm/đánh dấu hành động, xác minh hiệu lực §8.7).
 * QM: admin/leader luôn được; staff CHỈ khi is_quality_manager (giống pattern is_dept_lead).
 */
export function canManageCapa(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  return user.role === 'staff' && !!user.is_quality_manager;
}
/** Chạy CRON-7 nhắc CAPA thủ công: chỉ admin. */
export function canRunCapaCron(user: CurrentUser | null): boolean {
  return user?.role === 'admin';
}

// ── M10: Rủi ro & Cải tiến (EPIC-QMS §8.5/§8.6) ─────────────────
export function canViewRisk(user: CurrentUser | null): boolean {
  return hasPermission(user, 'risk', 'read') || (!!user && !isOffice(user));
}
export function canCreateRisk(user: CurrentUser | null): boolean {
  return hasPermission(user, 'risk', 'create') || user?.role === 'admin';
}
/** Quản lý rủi ro (biện pháp xử lý, đóng): QM (admin/leader hoặc staff is_quality_manager). */
export function canManageRisk(user: CurrentUser | null): boolean {
  if (!user) return false;
  if (user.role === 'admin' || user.role === 'leader') return true;
  return user.role === 'staff' && !!user.is_quality_manager;
}
export function canRunRiskCron(user: CurrentUser | null): boolean {
  return user?.role === 'admin';
}
export function canViewImprovement(user: CurrentUser | null): boolean {
  return hasPermission(user, 'improvement', 'read') || (!!user && !isOffice(user));
}
export function canCreateImprovement(user: CurrentUser | null): boolean {
  return hasPermission(user, 'improvement', 'create') || user?.role === 'admin';
}

// ── GĐ3: Kho biểu mẫu VILAS ─────────────────────────────────────
/** Xem/tải kho biểu mẫu: mọi vai trò có quyền form:read (KTV/lab_manager/qms/reception/admin/leader). */
export function canViewForms(user: CurrentUser | null): boolean {
  return hasPermission(user, 'form', 'read') || user?.role === 'admin';
}
/** Quản trị biểu mẫu gốc (thêm/sửa/tải lên template): QLCL + admin. */
export function canManageForms(user: CurrentUser | null): boolean {
  return hasPermission(user, 'form', 'manage') || user?.role === 'admin' || user?.role === 'qms';
}
/** Nộp minh chứng: KTV / trưởng phòng lab (form:submit theo phòng). */
export function canSubmitForms(user: CurrentUser | null): boolean {
  return hasPermission(user, 'form', 'submit') || user?.role === 'admin';
}

/**
 * Đăng ký lab (SV đăng ký sử dụng PTN, do người hướng dẫn duyệt): admin/leader/lab_manager,
 * giống canViewMentorship — không phải việc của Văn phòng/Phòng nhận mẫu.
 */
export function canViewLabReg(user: CurrentUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'leader' || user?.role === 'lab_manager';
}

// ── M19: Thẻ vào PTN (sinh viên) — KHÁC "Đăng ký lab" (NCKH, có duyệt) ở trên.
/** Xem danh sách thẻ vào PTN: admin/leader/qms/office (lab_access_card:read). */
export function canViewLabAccessCards(user: CurrentUser | null): boolean {
  return hasPermission(user, 'lab_access_card', 'read') || user?.role === 'admin';
}
/** Thêm/sửa/xóa thẻ vào PTN: Văn phòng + admin (lab_access_card:manage). */
export function canManageLabAccessCards(user: CurrentUser | null): boolean {
  return hasPermission(user, 'lab_access_card', 'manage') || user?.role === 'admin';
}

// ── GĐ2b: Nhận & Chuyển mẫu ─────────────────────────────────────
/** Xem phiếu nhận/chuyển mẫu (reception/lab/qms/leader/admin). */
export function canViewIntake(user: CurrentUser | null): boolean {
  return hasPermission(user, 'intake', 'read') || user?.role === 'admin';
}
/** Nhận mẫu & phân chỉ tiêu chuyển phòng lab (Phòng nhận mẫu + admin). */
export function canManageIntake(user: CurrentUser | null): boolean {
  return hasPermission(user, 'intake', 'manage') || user?.role === 'admin' || user?.role === 'reception';
}
/** Đổi trạng thái phiếu chuyển (phòng lab: KTV/trưởng phòng). */
export function canUpdateDispatch(user: CurrentUser | null): boolean {
  return hasPermission(user, 'dispatch', 'update') || user?.role === 'admin';
}

// ── m25: Báo cáo hoạt động hàng tháng ───────────────────────────
/**
 * Người NỘP báo cáo tháng (giảng viên/leader/lãnh đạo/KTV) = admin/leader/lab_manager/staff.
 * Văn phòng KHÔNG nộp — họ là bên tổng hợp.
 */
export function canSubmitActivityReport(user: CurrentUser | null): boolean {
  return !!user && ['admin', 'leader', 'lab_manager', 'staff'].includes(user.role);
}
/** Xem DANH SÁCH báo cáo tháng: người nộp (thấy của mình) + văn phòng/lãnh đạo (thấy tất cả). */
export function canViewActivityReports(user: CurrentUser | null): boolean {
  return !!user && ['admin', 'leader', 'lab_manager', 'staff', 'office'].includes(user.role);
}
/** Duyệt/tổng hợp báo cáo (submitted → reviewed): văn phòng + admin/leader. */
export function canReviewActivityReports(user: CurrentUser | null): boolean {
  return !!user && ['admin', 'leader', 'office'].includes(user.role);
}

// ── m27: Danh mục CHỈ TIÊU THỬ NGHIỆM (bảng giá phân tích) ───────
/** Toàn quyền thêm/sửa/xóa: Phòng nhận mẫu + Ban lãnh đạo + Quản trị. */
export function canManageTestParameters(user: CurrentUser | null): boolean {
  return !!user && ['reception', 'leader', 'admin'].includes(user.role);
}
/** Xem danh mục: mọi vai trò đã đăng nhập (dùng để chọn chỉ tiêu khi chuyển mẫu). */
export function canViewTestParameters(user: CurrentUser | null): boolean {
  return !!user;
}

// ── m29: Báo giá ────────────────────────────────────────────────
/** Lập/sửa/xóa báo giá: Phòng nhận mẫu + Quản trị + Ban lãnh đạo. */
export function canManageQuotations(user: CurrentUser | null): boolean {
  return !!user && ['reception', 'admin', 'leader'].includes(user.role);
}
/** Xem báo giá: mọi vai trò đã đăng nhập. */
export function canViewQuotations(user: CurrentUser | null): boolean {
  return !!user;
}

export const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'admin', label: 'Quản trị viên' },
  { value: 'leader', label: 'Ban lãnh đạo' },
  { value: 'reception', label: 'Phòng nhận mẫu' },
  { value: 'qms', label: 'Quản lý chất lượng' },
  { value: 'lab_manager', label: 'Trưởng phòng lab' },
  { value: 'staff', label: 'KTV' },
  { value: 'office', label: 'Văn phòng' },
];
