/**
 * Domain types — khớp backend LIMS VILAS (M1 mẫu, M2 hóa chất, M7 nền tảng).
 * Số thập phân (qty_base, balance_after, unit_price, stock_value...) là STRING — không parseFloat.
 */

// ── Roles & Auth ────────────────────────────────────────────────
export type Role =
  | 'admin'
  | 'leader'
  | 'office'
  | 'staff'
  | 'reception'
  | 'qms'
  | 'lab_manager';

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Quản trị viên',
  leader: 'Ban lãnh đạo',
  office: 'Văn phòng',
  staff: 'KTV',
  reception: 'Phòng nhận mẫu',
  qms: 'Quản lý chất lượng',
  lab_manager: 'Trưởng phòng lab',
};

/** m30 — 'pending' = tự đăng ký, chờ Quản trị viên duyệt (chưa đăng nhập được). */
export type UserStatus = 'active' | 'disabled' | 'pending';

export interface Permission {
  resource: string;
  action: string;
  scope?: string;
}

/** /auth/me — user hiện tại kèm ma trận quyền. */
export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department: { id: string; name: string; code: string } | null;
  is_dept_lead: boolean;
  /** M8: Phụ trách chất lượng (QM) — mở/đóng CAPA. admin/leader luôn có quyền QMS. */
  is_quality_manager?: boolean;
  status: UserStatus;
  must_change_password?: boolean;
  /** m30 — presigned URL ảnh đại diện (TTL 15 phút). null nếu chưa đặt ảnh. */
  avatar_url?: string | null;
  /** m30 — mốc xác thực email. null = chưa xác thực. */
  email_verified_at?: string | null;
  permissions: Permission[];
  created_at: string;
}

/** user tóm tắt trả về từ /auth/login. */
export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department_id: string | null;
  department_name: string | null;
  is_dept_lead: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  must_change_password?: boolean;
  user: AuthUser;
}

// ── Users (M7) ──────────────────────────────────────────────────
export interface UserListItem {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department_id: string | null;
  department_name: string | null;
  is_dept_lead: boolean;
  status: UserStatus;
  /** m30 — null nghĩa là người dùng chưa bấm link xác thực trong mail. */
  email_verified_at?: string | null;
  last_login_at?: string | null;
  created_at: string;
}

// ── Departments (M7) ────────────────────────────────────────────
export type DepartmentKind = 'leadership' | 'reception' | 'office' | 'qms' | 'division' | 'lab';

export const DEPARTMENT_KIND_LABELS: Record<DepartmentKind, string> = {
  leadership: 'Ban lãnh đạo',
  reception: 'Phòng nhận mẫu',
  office: 'Văn phòng',
  qms: 'Quản lý chất lượng',
  division: 'Phòng nghiên cứu trọng điểm',
  lab: 'Phòng thí nghiệm',
};

export interface Department {
  id: string;
  name: string;
  code: string;
  parent_id: string | null;
  kind?: DepartmentKind;
  is_vlab?: boolean;
  lead_user_id: string | null;
  lead_user_name?: string | null;
  status: string;
  member_count?: number;
  created_at?: string;
  children?: Department[];
}

// ── Kho biểu mẫu VILAS (GĐ3) ────────────────────────────────────
export type FormCategory = 'BM' | 'QT' | 'HD' | 'TL';

export const FORM_CATEGORY_LABELS: Record<FormCategory, string> = {
  BM: 'Biểu mẫu',
  QT: 'Quy trình',
  HD: 'Hướng dẫn',
  TL: 'Tài liệu',
};

export interface FormFile {
  id: string;
  file_name: string;
  mime: string | null;
  size: number | null;
  uploaded_at: string;
}

/** Nhóm tệp thuộc biểu mẫu gốc hay minh chứng — khớp path /forms/{owner}/{id}/file. */
export type FormFileOwner = 'templates' | 'submissions';

/** Một bản trong lịch sử tải lên của biểu mẫu/minh chứng (gồm cả bản đã bị thay). */
export interface FormFileHistoryItem extends FormFile {
  uploaded_by_name: string | null;
  /** true nếu đây là tệp đang dùng; false là bản đã bị thay/gỡ. */
  is_current: boolean;
  /** Thời điểm bị thay/gỡ — null khi vẫn là bản hiện hành. */
  replaced_at: string | null;
  action: string;
  action_label: string;
  /** Lý do người dùng nhập khi tải bản này lên. */
  reason: string | null;
  /** Lý do của thao tác đã loại bỏ bản này. */
  removed_reason: string | null;
}

export interface FormTemplate {
  id: string;
  code: string;
  title: string;
  iso_clause: string;
  category: FormCategory;
  year: number | null;
  is_active: boolean;
  note: string | null;
  files: FormFile[];
  created_at: string;
}

export interface FormSubmission {
  id: string;
  template_id: string;
  template_code: string | null;
  template_title: string | null;
  department_id: string;
  department_name: string | null;
  year: number | null;
  note: string | null;
  submitted_by: string;
  submitted_by_name: string | null;
  submitted_at: string;
  files: FormFile[];
  status: RegistrationStatus;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
}

// ── Nhận & Chuyển mẫu (GĐ2b) ────────────────────────────────────
// m28: luồng thật — tiếp nhận → báo giá → khách đồng ý → thanh toán → chuyển lab → trả KQ
export type IntakeStatus =
  | 'received' | 'quoted' | 'quote_accepted' | 'paid' | 'dispatched' | 'completed' | 'cancelled';

export const INTAKE_STATUS_LABELS: Record<IntakeStatus, string> = {
  received: 'Đã tiếp nhận',
  quoted: 'Đã báo giá',
  quote_accepted: 'Khách đồng ý giá',
  paid: 'Đã thanh toán',
  dispatched: 'Đã chuyển lab',
  completed: 'Đã trả kết quả',
  cancelled: 'Đã hủy',
};

/** Các bước theo thứ tự để vẽ thanh tiến trình (không gồm 'cancelled'). */
export const INTAKE_FLOW: IntakeStatus[] = [
  'received', 'quoted', 'quote_accepted', 'paid', 'dispatched', 'completed',
];

export type PaymentStatus = 'unpaid' | 'partial' | 'paid' | 'waived';
export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  unpaid: 'Chưa thanh toán',
  partial: 'Thanh toán một phần',
  paid: 'Đã thanh toán',
  waived: 'Miễn phí',
};

export type DispatchStatus = 'sent' | 'received' | 'in_progress' | 'done' | 'returned';
export const DISPATCH_STATUS_LABELS: Record<DispatchStatus, string> = {
  sent: 'Chờ tiếp nhận',
  received: 'Đã tiếp nhận',
  in_progress: 'Đang thực hiện',
  done: 'Hoàn thành',
  returned: 'Trả lại',
};

export interface SampleDispatch {
  id: string;
  intake_id: string;
  /** m27: liên kết danh mục chỉ tiêu (null = chỉ tiêu nhập tự do). */
  test_parameter_id?: string | null;
  unit_price?: string | null;
  /** m28 — BM 7.1.02: Loại/Tên mẫu + Số lượng. */
  sample_name?: string | null;
  quantity?: number;
  intake_code?: string | null;
  customer_name?: string | null;
  chi_tieu: string;
  don_vi?: string | null;
  phuong_phap?: string | null;
  ket_qua?: string | null;
  can_bo?: string | null;
  target_department_id: string;
  target_department_name: string | null;
  status: DispatchStatus;
  note: string | null;
  dispatched_by: string;
  dispatched_by_name: string | null;
  dispatched_at: string;
  received_at: string | null;
  completed_at: string | null;
  updated_at: string;
  files: FormFile[];
}

export interface SampleIntake {
  id: string;
  code: string;
  customer_name: string;
  contact: string | null;
  description: string | null;
  note: string | null;
  status: IntakeStatus;
  status_label?: string;
  /** Bước hợp lệ kế tiếp (backend trả) — FE dựng nút chuyển trạng thái. */
  next_statuses?: IntakeStatus[];
  payment_status?: PaymentStatus;
  paid_amount?: string | null;
  payment_date?: string | null;
  payment_ref?: string | null;
  payment_note?: string | null;
  /** Ô "Lưu ý" trên phiếu chuyển mẫu BM 7.1.02. */
  dispatch_note?: string | null;
  address?: string | null;
  tax_code?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  due_date?: string | null;
  result_language?: string | null;
  return_method?: string | null;
  fee_note?: string | null;
  other_request?: string | null;
  department_id: string | null;
  department_name: string | null;
  received_by: string;
  received_by_name: string | null;
  received_at: string;
  created_at: string;
  files: FormFile[];
  dispatches?: SampleDispatch[];
  /** m26: true = thông tin KH đang bị ẩn với vai trò hiện tại (phòng lab chưa được duyệt). */
  customer_info_masked?: boolean;
  /** 'pending' nếu phòng đã gửi yêu cầu và đang chờ Phòng nhận mẫu duyệt. */
  customer_info_request_status?: 'pending' | null;
}

// ── m29: BÁO GIÁ ─────────────────────────────────────────────────
export type QuotationStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired';

export const QUOTATION_STATUS_LABELS: Record<QuotationStatus, string> = {
  draft: 'Nháp',
  sent: 'Đã gửi khách',
  accepted: 'Khách đồng ý',
  rejected: 'Khách từ chối',
  expired: 'Hết hiệu lực',
};

export interface QuotationItem {
  id?: string;
  sort_order?: number;
  sample_name: string | null;
  test_parameter_id?: string | null;
  parameter_name: string;
  method?: string | null;
  unit?: string | null;
  quantity: number;
  /** Số tiền dạng STRING — không parseFloat để tránh sai số. */
  unit_price: string;
  amount?: string;
  note?: string | null;
}

export interface Quotation {
  id: string;
  code: string;
  intake_id: string | null;
  intake_code: string | null;
  customer_name: string;
  customer_address: string | null;
  customer_email: string | null;
  customer_phone: string | null;
  issue_date: string | null;
  valid_until: string | null;
  vat_rate: string;
  subtotal: string;
  vat_amount: string;
  total: string;
  status: QuotationStatus;
  status_label?: string;
  next_statuses?: QuotationStatus[];
  note: string | null;
  created_by_name?: string | null;
  created_at: string;
  updated_at: string;
  items?: QuotationItem[];
  item_count?: number;
}

// ── m27: Master data CHỈ TIÊU THỬ NGHIỆM (bảng giá phân tích) ────
export type TestMatrix =
  | 'soil' | 'water' | 'fertilizer' | 'feed' | 'food' | 'quarantine' | 'molecular' | 'other';

export const TEST_MATRIX_LABELS: Record<TestMatrix, string> = {
  soil: 'Đất',
  water: 'Nước',
  fertilizer: 'Phân bón, Chế phẩm sinh học',
  feed: 'Thức ăn chăn nuôi',
  food: 'Nông sản, Thực phẩm',
  quarantine: 'Kiểm dịch thực vật',
  molecular: 'Sinh học phân tử (SHPT)',
  other: 'Khác',
};

export interface TestParameter {
  id: string;
  matrix: TestMatrix;
  matrix_label: string;
  sample_matrix: string | null;
  name: string;
  method: string | null;
  unit: string | null;
  /** Số thập phân dạng STRING — không parseFloat để tránh sai số. */
  unit_price: string | null;
  currency: string;
  turnaround_days: number | null;
  in_charge: string | null;
  note: string | null;
  department_id: string | null;
  department_name: string | null;
  is_accredited: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── m26: Yêu cầu xem thông tin khách hàng ────────────────────────
export type InfoRequestStatus = 'pending' | 'approved' | 'rejected';

export const INFO_REQUEST_STATUS_LABELS: Record<InfoRequestStatus, string> = {
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
};

export interface CustomerInfoRequest {
  id: string;
  intake_id: string;
  intake_code: string | null;
  requester_user_id: string;
  requester_name: string | null;
  department_id: string | null;
  department_name: string | null;
  reason: string | null;
  status: InfoRequestStatus;
  decided_by: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  decide_note: string | null;
  created_at: string;
}

// ── Customers (M7) ──────────────────────────────────────────────
export type CustomerType = 'company' | 'individual' | 'internal' | 'external' | 'organization';

export const CUSTOMER_TYPE_LABELS: Record<string, string> = {
  company: 'Công ty',
  organization: 'Tổ chức',
  individual: 'Cá nhân',
  internal: 'Nội bộ',
  external: 'Bên ngoài',
};

export interface Customer {
  id: string;
  name: string;
  contact: string | null;
  type: string;
  note?: string | null;
  created_at?: string;
}

// ── Notifications (M7) ──────────────────────────────────────────
export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  ref_type: string | null;
  ref_id: string | null;
  read_at: string | null;
  created_at: string;
}

// ── Audit logs (M7) ─────────────────────────────────────────────
export interface AuditLog {
  id: string;
  user_id: string;
  user_name: string;
  action: string;
  resource: string;
  resource_id: string | null;
  correlation_id: string | null;
  ip: string | null;
  at: string;
  detail?: Record<string, unknown>;
}

// ── Roles meta ──────────────────────────────────────────────────
export interface RoleMeta {
  role: Role;
  label: string;
  description: string;
  scope: string;
}

// ── Units (M2) ──────────────────────────────────────────────────
export type MeasurementGroup = 'mass' | 'volume' | 'count';

export const MEASUREMENT_GROUP_LABELS: Record<MeasurementGroup, string> = {
  mass: 'Khối lượng',
  volume: 'Thể tích',
  count: 'Đếm',
};

export interface Unit {
  code: string;
  group: MeasurementGroup;
  factor_to_base: string;
  label: string;
}

// ── Chemicals (M2) ──────────────────────────────────────────────
export type ChemicalStatus = 'active' | 'inactive';

export interface Chemical {
  id: string;
  name: string;
  cas_no: string | null;
  manufacturer: string | null;
  base_unit: string;
  measurement_group: MeasurementGroup;
  hazard_code: string | null;
  department_id: string | null;
  department_name: string | null;
  reorder_threshold: string | null;
  total_stock_base: string;
  status: ChemicalStatus;
  lot_count: number;
  has_expiring_lot: boolean;
  created_at: string;
}

export interface Lot {
  id: string;
  lot_no: string;
  qty_base: string;
  base_unit: string;
  qty_display?: string;
  display_unit?: string;
  received_at?: string | null;
  expiry_date?: string | null;
  recheck_date?: string | null;
  recheck_result?: 'pass' | 'fail' | null;
  is_expired?: boolean;
  has_coa?: boolean;
  // chỉ vai trò tài chính:
  unit_price?: string;
  price_unit?: string;
  currency?: string;
  stock_value?: string;
}

export interface StockLot {
  lot_id: string;
  lot_no: string;
  qty_base: string;
  qty_display: string;
  unit_price?: string;
  price_unit?: string;
  stock_value?: string;
}

export interface Stock {
  chemical_id: string;
  chemical_name: string;
  base_unit: string;
  measurement_group: MeasurementGroup;
  display_unit: string;
  total_stock_base: string;
  total_stock_display: string;
  total_stock_value?: string;
  currency?: string;
  lots: StockLot[];
}

export type TransactionType = 'in' | 'out' | 'adjust';

export const TXN_TYPE_LABELS: Record<TransactionType, string> = {
  in: 'Nhập',
  out: 'Xuất',
  adjust: 'Điều chỉnh',
};

export interface Transaction {
  id: string;
  lot_id: string;
  lot_no: string;
  chemical_id: string;
  chemical_name: string;
  type: TransactionType;
  qty_input: string;
  input_unit: string;
  qty_base: string;
  base_unit: string;
  balance_after: string;
  ref_sample_id?: string | null;
  ref_sample_code?: string | null;
  warning_override: boolean;
  by_user_name: string;
  at: string;
  note: string | null;
  // chỉ vai trò tài chính:
  unit_price?: string;
  currency?: string;
  line_value?: string;
}

export interface LowStockItem {
  chemical_id: string;
  chemical_name: string;
  base_unit: string;
  total_stock_base: string;
  reorder_threshold: string;
  department_name: string | null;
  alert_open: boolean;
}

// ── Samples (M1) ────────────────────────────────────────────────
export type SampleStatus = 'received' | 'assigned' | 'testing' | 'done' | 'overdue' | 'returned';

export const SAMPLE_STATUS_LABELS: Record<SampleStatus, string> = {
  received: 'Đã tiếp nhận',
  assigned: 'Đã phân công',
  testing: 'Đang thực nghiệm',
  done: 'Đã chốt',
  overdue: 'Quá hạn',
  returned: 'Đã trả kết quả',
};

export type RequestStatus = 'draft' | 'active';

export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  draft: 'Nháp',
  active: 'Đang xử lý',
};

export interface TestRequestListItem {
  id: string;
  request_code: string;
  customer_id: string | null;
  customer_name: string | null;
  sender_name: string;
  department_id: string | null;
  department_name: string | null;
  received_by: string | null;
  received_by_name: string | null;
  received_at: string;
  sample_count: number;
  status: RequestStatus;
  created_at: string;
}

export interface RequestSample {
  id: string;
  sample_code: string;
  status: SampleStatus;
  deadline_at: string;
  condition_status: string | null;
}

export interface TestRequestDetail {
  id: string;
  request_code: string;
  customer: { id: string; name: string; contact: string | null } | null;
  sender_name: string;
  department_id: string | null;
  department_name: string | null;
  received_by_name: string | null;
  received_at: string;
  note: string | null;
  status: RequestStatus;
  samples: RequestSample[];
  created_at: string;
}

export interface SampleListItem {
  id: string;
  sample_code: string;
  request_code: string;
  department_name: string;
  status: SampleStatus;
  deadline_at: string;
  is_overdue: boolean;
  current_custodian_name: string | null;
  assignment_count: number;
  approved_count: number;
  created_at: string;
}

export type AssignmentStatus = 'assigned' | 'in_progress' | 'result_entered' | 'approved';

export interface Assignment {
  id: string;
  sample_id?: string;
  part_name: string;
  assigned_to: string;
  assigned_to_name: string;
  assigned_by_name: string;
  status: AssignmentStatus;
  assigned_at: string;
}

export interface SampleDetail {
  id: string;
  sample_code: string;
  request_id: string;
  request_code: string;
  customer_name: string | null;
  department_id: string;
  department_name: string;
  description: string;
  received_at: string;
  deadline_at: string;
  status: SampleStatus;
  is_overdue: boolean;
  completed_at: string | null;
  condition_status: string | null;
  condition_note: string | null;
  current_custodian: { id: string; name: string } | null;
  assignments: Assignment[];
  can_finalize: boolean;
  created_at: string;
}

export type ApprovalStatus = 'pending' | 'approved' | 'returned';

export interface SampleResultItem {
  assignment_id: string;
  part_name: string;
  version?: number;
  approval_status: ApprovalStatus;
  is_published: boolean;
  result_data: Record<string, unknown> | null;
  entered_by_name?: string;
  approved_by_name?: string;
  note?: string;
}

export interface CustodyEntry {
  custodian_id: string;
  custodian_name: string;
  from: string;
  to: string | null;
  reason: string;
  is_current?: boolean;
}

export interface AssignmentResult {
  id: string;
  assignment_id: string;
  part_name: string;
  version: number;
  is_current: boolean;
  result_data: Record<string, unknown>;
  entered_by_name: string;
  entered_at: string;
  approved_by_name: string | null;
  approved_at: string | null;
  approval_status: ApprovalStatus;
  attachments?: { id: string; file_name: string; mime: string; size: number }[];
}

export interface OverdueSample {
  id: string;
  sample_code: string;
  department_name: string;
  status: SampleStatus;
  deadline_at: string;
  days_overdue: number;
  has_overdue_reason: boolean;
  assignee_names: string[];
}

// ── Attachments (chung) ─────────────────────────────────────────
export interface Attachment {
  id: string;
  owner_type: string;
  owner_id: string;
  file_name: string;
  mime: string;
  size: number;
  download_url?: string;
  url_expires_at?: string;
  uploaded_by_name?: string;
  uploaded_at: string;
}

// ── M4: Nhân sự (HR) ────────────────────────────────────────────
/**
 * Hồ sơ nhân sự. Các trường tài chính (salary_*, contract_*, computed_salary_amount,
 * next/last_salary_raise_date, currency) và PII (id_number, dob, bank_account)
 * VẮNG MẶT (không null) khi người gọi không đủ quyền — luôn dùng `'field' in obj`.
 * Số tiền / hệ số là STRING — không parseFloat.
 */
export interface HrProfile {
  user_id: string;
  full_name: string;
  email?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  job_title?: string | null;
  position?: string | null;
  hired_date?: string | null;
  phone?: string | null;
  salary_cycle_years?: number;
  created_at?: string;
  // ── PII (strip) ──
  id_number?: string;
  dob?: string;
  bank_account?: string;
  // ── Hợp đồng (strip nhóm contract_*) ──
  contract_signed_date?: string | null;
  contract_type?: string | null;
  contract_end_date?: string | null;
  // ── Lương (strip nhóm tài chính) ──
  salary_grade?: string;
  salary_coefficient?: string;
  base_salary_amount?: string;
  computed_salary_amount?: string;
  currency?: string;
  last_salary_raise_date?: string | null;
  next_salary_raise_date?: string | null;
}

export interface SalaryHistoryItem {
  id: string;
  old_grade: string | null;
  old_coefficient: string | null;
  old_base_amount: string | null;
  new_grade: string;
  new_coefficient: string;
  new_base_amount: string;
  raise_date: string;
  by_user_id: string | null;
  by_user_name: string | null;
  note: string | null;
  created_at: string;
}

export type CompetenceKind = 'degree' | 'certificate' | 'authorization';

export const COMPETENCE_KIND_LABELS: Record<CompetenceKind, string> = {
  degree: 'Bằng cấp',
  certificate: 'Chứng chỉ',
  authorization: 'Ủy quyền thử nghiệm',
};

export interface Competence {
  id: string;
  kind: CompetenceKind;
  title: string;
  issuer: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  scope_detail: string | null;
  authorized_by_user_id: string | null;
  authorized_by_name: string | null;
  is_expired: boolean;
  attachment_id: string | null;
}

export interface CompetenceSummary {
  user_id: string;
  full_name: string;
  department_name: string | null;
  job_title: string | null;
  degrees: { title: string; issuer?: string | null; issued_date?: string | null; is_expired?: boolean }[];
  certificates: { title: string; issuer?: string | null; expiry_date?: string | null; is_expired?: boolean }[];
  authorizations: { title: string; expiry_date?: string | null; is_expired?: boolean }[];
  research_summary: { projects: number; publications: number; patents: number; mentorships: number };
}

// ── M4: NCKH ────────────────────────────────────────────────────
export interface CatalogItem {
  code: string;
  label: string;
}

/** Thành viên đề tài — HOẶC user_id (nội bộ) HOẶC external_name (ngoài hệ thống). */
export interface ProjectMember {
  user_id: string | null;
  external_name?: string | null;
  name?: string | null;
  role_in_project: string | null;
}

export interface ResearchProject {
  id: string;
  code?: string | null;
  title: string;
  level: string;
  lead_user_id: string | null;
  lead_user_name: string | null;
  lead_external_name?: string | null;
  department_id: string | null;
  department_name: string | null;
  start_date: string | null;
  end_date: string | null;
  academic_year?: string | null;
  budget_amount?: string | null;
  budget_currency?: string | null;
  is_transferred?: boolean;
  transfer_product?: string | null;
  status: string;
  member_count?: number;
  members?: ProjectMember[];
}

export type PublicationType = 'paper' | 'patent' | 'conference';
export type PubScope = 'domestic' | 'international';
export type AuthorRole = 'main' | 'co' | 'corresponding';

export const PUBLICATION_TYPE_LABELS: Record<PublicationType, string> = {
  paper: 'Bài báo',
  patent: 'Sáng chế / GPHI',
  conference: 'Báo cáo hội nghị/kỷ yếu',
};

export const AUTHOR_ROLE_LABELS: Record<AuthorRole, string> = {
  main: 'Tác giả',
  co: 'Đồng tác giả',
  corresponding: 'Tác giả liên hệ',
};

/** Tác giả — HOẶC user_id (nội bộ) HOẶC external_name (ngoài hệ thống). */
export interface PublicationAuthor {
  user_id: string | null;
  external_name?: string | null;
  name?: string | null;
  author_order: number;
  is_corresponding: boolean;
  author_role?: AuthorRole | null;
}

export interface Publication {
  id: string;
  type: PublicationType;
  title: string;
  journal: string | null;
  year: number;
  doi: string | null;
  index_code: string | null;
  category: string | null;
  pub_scope?: PubScope | null;
  is_scie?: boolean;
  is_ssci?: boolean;
  is_scopus?: boolean;
  is_aci?: boolean;
  academic_year?: string | null;
  department_id: string | null;
  department_name: string | null;
  patent_no: string | null;
  issuing_authority: string | null;
  application_no?: string | null;
  application_date?: string | null;
  granted_date?: string | null;
  patent_holder?: string | null;
  authors: PublicationAuthor[];
}

export interface StudentMentorship {
  id: string;
  mentor_id: string;
  mentor_name: string | null;
  student_name: string;
  topic: string | null;
  year: number;
  type: string;
  department_id: string | null;
  department_name?: string | null;
}

export type RegistrationStatus = 'pending' | 'approved' | 'rejected';

export const REGISTRATION_STATUS_LABELS: Record<RegistrationStatus, string> = {
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Đã từ chối',
};

export interface LabRegistration {
  id: string;
  student_name: string;
  mentor_id: string;
  mentor_name: string | null;
  registered_from: string;
  registered_to: string | null;
  purpose: string;
  status: RegistrationStatus;
  department_id: string | null;
  decided_by_user_id: string | null;
  decided_at: string | null;
  created_at: string;
}

/** Thẻ vào PTN (sinh viên) — danh sách quản trị do Văn phòng quản lý, không qua duyệt. */
export interface LabAccessCard {
  id: string;
  student_name: string;
  class_name: string | null;
  student_code: string;
  email: string | null;
  room: string;
  purpose: string | null;
  supervisor_name: string | null;
  valid_from: string;
  valid_to: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeachingCourse {
  id: string;
  user_id: string | null;
  user_name?: string | null;
  lecturer_external_name?: string | null;
  course_name: string;
  semester: string;
  year: number;
  academic_year?: string | null;
  hk1_theory_hours?: number | null;
  hk1_practice_hours?: number | null;
  hk2_theory_hours?: number | null;
  hk2_practice_hours?: number | null;
  note?: string | null;
  department_id?: string | null;
  department_name?: string | null;
}

// ── Menu mới (migration m23) ─────────────────────────────────────
export interface ResearchContract {
  id: string;
  title: string;
  contract_type: string | null;
  value_amount: string | null;
  currency: string | null;
  partner_org: string | null;
  start_date: string | null;
  end_date: string | null;
  academic_year: string | null;
  department_id: string | null;
  department_name?: string | null;
  created_at?: string;
}

export type StaffActivityKind = 'dang' | 'cong_doan' | 'vilas' | 'khac';

export const STAFF_ACTIVITY_KIND_LABELS: Record<StaffActivityKind, string> = {
  dang: 'Công tác Đảng',
  cong_doan: 'Công tác Công đoàn',
  vilas: 'Công tác VILAS',
  khac: 'Khác',
};

export interface StaffActivity {
  id: string;
  kind: StaffActivityKind;
  content: string;
  performed_at: string | null;
  academic_year: string | null;
  performer_user_id: string | null;
  performer_name?: string | null;
  department_id: string | null;
  created_at?: string;
}

export interface TrainingCertificate {
  id: string;
  recipient_name: string;
  certificate_no: string | null;
  course_name: string | null;
  issued_date: string | null;
  note: string | null;
  academic_year: string | null;
  host_user_id: string | null;
  host_name?: string | null;
  department_id: string | null;
  created_at?: string;
}

export interface CommunityService {
  id: string;
  content: string;
  performed_at: string;
  host: string | null;
  performer_user_id: string;
  performer_name?: string | null;
  department_id?: string | null;
  department_name?: string | null;
}

export interface AchievementStats {
  group_by: 'individual' | 'department';
  user_id?: string | null;
  user_name?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  period: { from: string | null; to: string | null };
  projects: { total: number; by_level: Record<string, number> };
  publications: { total: number; by_index: Record<string, number> };
  patents: number;
  mentorships: number;
  lab_registrations_approved: number;
  teaching_courses: number;
  community_services: number;
}

// ── M3: Quản lý Tài liệu (Document Control) ─────────────────────
export type DocumentType = 'SOP' | 'PROCEDURE' | 'FORM' | 'GUIDE' | 'STANDARD';

export type SecurityLevel = 'internal' | 'restricted';

export const SECURITY_LEVEL_LABELS: Record<SecurityLevel, string> = {
  internal: 'Nội bộ',
  restricted: 'Hạn chế',
};

export type DocVersionStatus = 'draft' | 'review' | 'approved' | 'obsolete';

export const DOC_VERSION_STATUS_LABELS: Record<DocVersionStatus, string> = {
  draft: 'Bản nháp',
  review: 'Chờ duyệt',
  approved: 'Hiệu lực',
  obsolete: 'Lỗi thời',
};

export interface DocumentTypeMeta {
  code: DocumentType;
  label: string;
  prefix: string;
}

export interface ConfidentialityLevel {
  code: SecurityLevel;
  label: string;
  description: string;
  is_default: boolean;
}

/** File đính kèm của 1 version (shape rút gọn trong các response M3). */
export interface DocVersionFile {
  attachment_id: string;
  filename: string;
  size: number;
  mime: string;
}

/** Version đầy đủ (chi tiết / tạo version / lịch sử). */
export interface DocumentVersion {
  id: string;
  document_id?: string;
  document_code?: string;
  version_no: number;
  status: DocVersionStatus;
  is_obsolete?: boolean;
  obsolete_label?: string | null;
  change_note?: string | null;
  created_by?: string;
  created_by_name?: string | null;
  created_at?: string;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  approved_by?: string | null;
  approved_by_name?: string | null;
  approved_at?: string | null;
  reject_reason?: string | null;
  file?: DocVersionFile | null;
}

/** Version hiệu lực tóm tắt trong list. */
export interface CurrentVersionSummary {
  id: string;
  version_no: number;
  status: DocVersionStatus;
  approved_at?: string | null;
  approved_by_name?: string | null;
}

export interface DocumentListItem {
  id: string;
  document_code: string;
  title: string;
  type: DocumentType;
  type_label: string;
  department_id: string | null;
  department_name: string | null;
  security_level: SecurityLevel;
  status: string;
  current_version: CurrentVersionSummary | null;
  created_at: string;
}

export interface DocumentDetail {
  id: string;
  document_code: string;
  title: string;
  type: DocumentType;
  type_label: string;
  department_id: string | null;
  department_name: string | null;
  security_level: SecurityLevel;
  status: string;
  current_version_id: string | null;
  created_by_name?: string | null;
  created_at: string;
  current_version: DocumentVersion | null;
  versions: DocumentVersion[];
}

/** Response tạo tài liệu (#4). */
export interface CreatedDocument {
  id: string;
  document_code: string;
  title: string;
  type: DocumentType;
  department_id: string | null;
  department_name: string | null;
  security_level: SecurityLevel;
  status: string;
  current_version_id: string | null;
  created_by?: string;
  created_at: string;
  first_version: DocumentVersion;
}

export interface DocStateChange {
  from: DocVersionStatus;
  to: DocVersionStatus;
}

/** Response duyệt version (#13). */
export interface ApproveVersionResult {
  id: string;
  version_no: number;
  status: DocVersionStatus;
  approved_by?: string;
  approved_by_name?: string | null;
  approved_at?: string | null;
  state_change: DocStateChange;
  document: {
    id: string;
    current_version_id: string | null;
    obsoleted_version: { id: string; version_no: number; status: DocVersionStatus } | null;
  };
}

/** Hàng đợi chờ duyệt (#17). */
export interface PendingReviewItem {
  document_id: string;
  document_code: string;
  title: string;
  department_name: string | null;
  version_id: string;
  version_no: number;
  status: DocVersionStatus;
  change_note: string | null;
  created_by_name: string | null;
  submitted_at: string | null;
  can_approve: boolean;
}

/** Response tải file version (#15) — presigned URL. */
export interface DownloadInfo {
  version_id: string;
  version_no: number;
  status: DocVersionStatus;
  is_obsolete: boolean;
  obsolete_warning: string | null;
  filename: string;
  mime: string;
  size: number;
  download_url: string;
  url_expires_at: string;
}

/** Lịch sử (#16). */
export interface HistoryEvent {
  action: string;
  by_name: string | null;
  at: string;
  detail?: string | null;
}
export interface HistoryVersionGroup {
  version_no: number;
  events: HistoryEvent[];
}
export interface DocumentHistory {
  document_id: string;
  document_code: string;
  timeline: HistoryVersionGroup[];
}

/** Thống kê truy cập 1 tài liệu (#18). */
export interface AccessStatsSeriesPoint {
  period: string;
  view: number;
  download: number;
  edit: number;
}
export interface DocumentAccessStats {
  document_id: string;
  document_code: string;
  range: { from: string; to: string };
  totals: { view: number; download: number; edit: number };
  series?: AccessStatsSeriesPoint[];
}

/** Thống kê truy cập tổng hợp (#19). */
export interface TopDocument {
  document_id: string;
  document_code: string;
  title: string;
  department_name: string | null;
  view: number;
  download: number;
  edit: number;
  total: number;
}
export interface AccessStatsAggregate {
  range: { from: string; to: string };
  summary: { total_view: number; total_download: number; total_edit: number; document_count: number };
  top_documents: TopDocument[];
}

// ── M5: Thiết bị & Hiệu chuẩn (Equipment & Calibration) ─────────
export type EquipmentStatus = 'active' | 'maintenance' | 'broken' | 'retired';

export const EQUIPMENT_STATUS_LABELS: Record<EquipmentStatus, string> = {
  active: 'Đang hoạt động',
  maintenance: 'Bảo trì',
  broken: 'Hỏng',
  retired: 'Ngưng sử dụng',
};

export type CalibrationCycleUnit = 'month' | 'year';

export const CALIBRATION_CYCLE_UNIT_LABELS: Record<CalibrationCycleUnit, string> = {
  month: 'tháng',
  year: 'năm',
};

export type CalibrationStatus =
  | 'not_applicable'
  | 'never_calibrated'
  | 'ok'
  | 'due_soon'
  | 'overdue'
  | 'failed';

export const CALIBRATION_STATUS_LABELS: Record<CalibrationStatus, string> = {
  not_applicable: 'Không diện hiệu chuẩn',
  never_calibrated: 'Chưa hiệu chuẩn',
  ok: 'Còn hạn',
  due_soon: 'Sắp tới hạn',
  overdue: 'Quá hạn',
  failed: 'Không đạt',
};

export type CalibrationResult = 'pass' | 'fail';

export const CALIBRATION_RESULT_LABELS: Record<CalibrationResult, string> = {
  pass: 'Đạt',
  fail: 'Không đạt',
};

/** Trường badge cảnh báo hiệu chuẩn — backend tính runtime, FE chỉ hiển thị. */
export interface CalibrationBadge {
  calibration_status: CalibrationStatus;
  is_overdue: boolean;
  days_to_due: number | null;
  warning_label: string | null;
}

/** Item danh sách thiết bị (#1) + danh sách quá hạn (#2). */
export interface EquipmentListItem extends CalibrationBadge {
  id: string;
  equipment_code: string;
  name: string;
  location?: string | null;
  department_id?: string | null;
  department_name: string | null;
  responsible_user_id?: string | null;
  responsible_user_name?: string | null;
  purchase_date?: string | null;
  status: EquipmentStatus;
  calibration_cycle_value?: number | null;
  calibration_cycle_unit?: CalibrationCycleUnit | null;
  next_due_date: string | null;
  last_calibrated_at?: string | null;
  last_calibration_result?: CalibrationResult | null;
  created_at?: string;
}

/** Tài liệu thiết bị đính kèm (owner_type='equipment'). */
export interface EquipmentAttachment {
  attachment_id: string;
  file_name: string;
  mime: string;
  size: number;
  doc_type?: string | null;
  uploaded_by_name?: string | null;
  uploaded_at: string;
}

/** Lần hiệu chuẩn gần nhất (rút gọn) trong chi tiết thiết bị. */
export interface LastCalibration {
  id: string;
  calibrated_at: string;
  provider: string | null;
  result: CalibrationResult;
  next_due_date: string | null;
  cert_attachment_id: string | null;
}

/** Chi tiết thiết bị (#3, #4 tạo, #5 sửa). */
export interface EquipmentDetail extends CalibrationBadge {
  id: string;
  equipment_code: string;
  name: string;
  location?: string | null;
  department_id: string | null;
  department_name: string | null;
  responsible_user_id?: string | null;
  responsible_user_name?: string | null;
  purchase_date?: string | null;
  status: EquipmentStatus;
  calibration_cycle_value?: number | null;
  calibration_cycle_unit?: CalibrationCycleUnit | null;
  next_due_date: string | null;
  last_calibration?: LastCalibration | null;
  calibration_count?: number;
  attachments?: EquipmentAttachment[];
  created_by_name?: string | null;
  created_at: string;
  updated_at?: string | null;
}

/** Bản ghi hiệu chuẩn — BẤT BIẾN (immutable, không sửa/xóa). */
export interface CalibrationRecord {
  id: string;
  equipment_id: string;
  equipment_code?: string;
  calibrated_at: string;
  provider: string | null;
  result: CalibrationResult;
  next_due_date: string | null;
  next_due_overridden?: boolean;
  override_reason?: string | null;
  is_latest: boolean;
  cert_attachment_id: string | null;
  cert_file_name?: string | null;
  note?: string | null;
  correction_of?: string | null;
  created_by_name?: string | null;
  created_at: string;
}

/** Thông tin tải file (presigned URL) — đính kèm thiết bị / cert hiệu chuẩn. */
export interface EquipmentDownloadInfo {
  file_name: string;
  mime: string;
  size: number;
  download_url: string;
  url_expires_at: string;
}

// ── M6: Báo cáo & Dashboard (Reporting & Analytics) ─────────────
/**
 * Dashboard tổng hợp chéo module (#1). Mỗi khối KPI có `available`.
 * Khối VẮNG MẶT khi vai trò không được xem (office: không `samples`/`equipments`/`documents`;
 * staff: không `hr`) — luôn dùng `'samples' in data` để kiểm tra, KHÔNG dựa null.
 * Field tiền (`consumption_cost_month`) chỉ có với vai trò tài chính (admin/leader/office).
 * Số tiền là number theo backend M6 (KPI đếm/tổng) — hiển thị qua formatNumber, không tính tiếp.
 */
export interface DashboardScope {
  role: Role;
  department_id: string | null;
  department_name?: string | null;
}

export interface DashboardSamplesKpi {
  available: boolean;
  error?: string;
  by_status?: Partial<Record<SampleStatus, number>>;
  total?: number;
  overdue?: number;
  deep_link?: string;
}

export interface DashboardChemicalsKpi {
  available: boolean;
  error?: string;
  expiring_soon?: number;
  recheck_due?: number;
  low_stock?: number;
  /** Chỉ vai trò tài chính (admin/leader/office). */
  consumption_cost_month?: number;
  deep_link_expiring?: string;
  deep_link_low_stock?: string;
}

export interface DashboardEquipmentsKpi {
  available: boolean;
  error?: string;
  calibration_overdue?: number;
  calibration_due_soon?: number;
  deep_link?: string;
}

export interface DashboardHrKpi {
  available: boolean;
  error?: string;
  salary_raise_due?: number;
  contract_ending?: number;
  deep_link?: string;
}

export interface DashboardDocumentsKpi {
  available: boolean;
  error?: string;
  pending_review?: number;
  deep_link?: string;
}

export interface DashboardNotificationsKpi {
  available: boolean;
  error?: string;
  unread?: number;
  deep_link?: string;
}

/** Khối KPI riêng cho dashboard vai trò qms (M21). */
export interface DashboardQmsKpi {
  available: boolean;
  error?: string;
  nc_open?: number;
  nc_open_capa?: number;
  risk_open_high?: number;
  evidence_pending?: number;
  improvements_open?: number;
  deep_link_nc?: string;
  deep_link_risk?: string;
  deep_link_evidence?: string;
  deep_link_improvements?: string;
}

export interface DashboardData {
  scope: DashboardScope;
  samples?: DashboardSamplesKpi;
  chemicals?: DashboardChemicalsKpi;
  equipments?: DashboardEquipmentsKpi;
  hr?: DashboardHrKpi;
  documents?: DashboardDocumentsKpi;
  notifications?: DashboardNotificationsKpi;
  qms?: DashboardQmsKpi;
}

/** meta của response aggregate M6 (cache + thời điểm). */
export interface DashboardMeta {
  generated_at: string;
  cached: boolean;
  cache_ttl_seconds?: number;
  from?: string;
  to?: string;
}

export interface DashboardResponse {
  data: DashboardData;
  meta: DashboardMeta;
}

// ── Charts (#2) ─────────────────────────────────────────────────
export interface ChartBlock<T> {
  available: boolean;
  error?: string;
  data?: T[];
}

export interface SamplesByStatusPoint {
  status: SampleStatus;
  count: number;
}

export interface SamplesOverTimePoint {
  period: string;
  count: number;
}

export interface ChemicalConsumptionPoint {
  period: string;
  qty: number;
  /** Chỉ vai trò tài chính. */
  cost?: number;
}

export interface ChemicalConsumptionGroup {
  measurement_group: MeasurementGroup;
  base_unit: string;
  data: ChemicalConsumptionPoint[];
}

export interface NcByStatusPoint {
  status: NcStatus;
  count: number;
}

export interface DashboardCharts {
  samples_by_status?: ChartBlock<SamplesByStatusPoint>;
  samples_over_time?: ChartBlock<SamplesOverTimePoint> & {
    group_by?: string;
    metric?: string;
  };
  nc_by_status?: ChartBlock<NcByStatusPoint>;
  chemical_consumption?: {
    available: boolean;
    error?: string;
    group_by?: string;
    by_measurement_group: ChemicalConsumptionGroup[];
  };
}

export interface DashboardChartsResponse {
  data: DashboardCharts;
  meta: DashboardMeta;
}

// ── Báo cáo mẫu (#3) ────────────────────────────────────────────
export interface SamplesReportData {
  filter: {
    from: string;
    to: string;
    department_id: string | null;
    time_field: string;
  };
  total: number;
  breakdown_by: 'status' | 'time' | 'department';
  by_status?: Partial<Record<SampleStatus, number>>;
  by_time?: { period: string; count: number }[];
  by_department?: { department_id: string; department_name: string; count: number }[];
}

export interface SamplesReportResponse {
  data: SamplesReportData;
  meta: DashboardMeta;
}

// ── Báo cáo hóa chất (#4) ───────────────────────────────────────
export interface ChemicalsReportGroup {
  measurement_group: MeasurementGroup;
  base_unit: string;
  total_qty: number;
  /** Chỉ vai trò tài chính. */
  consumption_cost?: number;
}

export interface ChemicalsReportData {
  filter: {
    from: string;
    to: string;
    department_id: string | null;
    metric: 'consumption' | 'stock';
  };
  by_measurement_group: ChemicalsReportGroup[];
  /** Chỉ vai trò tài chính. */
  total_cost?: number;
}

export interface ChemicalsReportResponse {
  data: ChemicalsReportData;
  meta: DashboardMeta;
}

// ── Thống kê truy cập hệ thống R15 (#10) ────────────────────────
export interface SystemAccessTopUser {
  user_id: string;
  user_name: string;
  count: number;
}

export interface SystemAccessTimelinePoint {
  period: string;
  access_count: number;
  download_count: number;
  edit_count: number;
}

export interface SystemAccessData {
  filter: { from: string; to: string };
  totals: { access_count: number; download_count: number; edit_count: number };
  breakdown_definition?: Record<string, string>;
  top_users: {
    access: SystemAccessTopUser[];
    download: SystemAccessTopUser[];
    edit: SystemAccessTopUser[];
  };
  timeline?: SystemAccessTimelinePoint[];
}

export interface SystemAccessResponse {
  data: SystemAccessData;
  meta: DashboardMeta;
}

// ── Chi tiết truy cập 1 user (#11) ──────────────────────────────
export interface SystemAccessUserAction {
  at: string;
  action: string;
  resource: string;
  resource_id: string | null;
  correlation_id?: string | null;
}

export interface SystemAccessUserData {
  user: { id: string; name: string; role: Role; department_name: string | null };
  filter: { from: string; to: string };
  totals: { access_count: number; download_count: number; edit_count: number };
  recent_actions: SystemAccessUserAction[];
}

export type ReportType = 'dashboard' | 'samples' | 'chemicals' | 'system-access';

// ── Pagination ──────────────────────────────────────────────────
export interface PageMeta {
  page: number;
  limit: number;
  total: number;
  hasNext: boolean;
}

export interface Paged<T> {
  data: T[];
  meta: PageMeta;
}

// ── M8: Không phù hợp & Hành động khắc phục (NC & CAPA §7.10/§8.7) ──
export type NcSource = 'manual' | 'complaint' | 'qc' | 'audit' | 'env' | 'sample' | 'pt';
export const NC_SOURCE_LABELS: Record<NcSource, string> = {
  manual: 'Nhập thủ công',
  complaint: 'Khiếu nại',
  qc: 'Kiểm soát chất lượng (QC)',
  audit: 'Đánh giá nội bộ',
  env: 'Điều kiện môi trường',
  sample: 'Mẫu thử nghiệm',
  pt: 'Thử nghiệm thành thạo',
};

export type NcSeverity = 'minor' | 'major' | 'critical';
export const NC_SEVERITY_LABELS: Record<NcSeverity, string> = {
  minor: 'Nhẹ',
  major: 'Nặng',
  critical: 'Nghiêm trọng',
};

export type NcStatus = 'open' | 'in_capa' | 'closed' | 'cancelled';
export const NC_STATUS_LABELS: Record<NcStatus, string> = {
  open: 'Mới mở',
  in_capa: 'Đang khắc phục',
  closed: 'Đã đóng',
  cancelled: 'Đã hủy',
};

export type CapaType = 'corrective' | 'preventive';
export const CAPA_TYPE_LABELS: Record<CapaType, string> = {
  corrective: 'Khắc phục',
  preventive: 'Phòng ngừa',
};

export type CapaStatus = 'in_progress' | 'closed';
export type CapaEffectiveness = 'effective' | 'not_effective';
export const CAPA_EFFECTIVENESS_LABELS: Record<CapaEffectiveness, string> = {
  effective: 'Hiệu lực đạt',
  not_effective: 'Chưa hiệu lực',
};
export type ActionStatus = 'todo' | 'done';

export interface NcListItem {
  id: string;
  nc_code: string;
  title: string;
  source_type: NcSource;
  source_label: string;
  severity: NcSeverity;
  status: NcStatus;
  department_id: string | null;
  department_name: string | null;
  raised_by_name: string | null;
  raised_at: string;
  has_capa: boolean;
}

export interface CapaActionItem {
  id: string;
  action: string;
  assignee_id: string | null;
  assignee_name: string | null;
  due_date: string | null;
  status: ActionStatus;
  done_at: string | null;
  note: string | null;
  created_at: string;
}

export interface CapaDetail {
  id: string;
  nc_id: string;
  capa_type: CapaType;
  root_cause: string;
  owner_id: string;
  owner_name: string | null;
  due_date: string | null;
  status: CapaStatus;
  effectiveness_result: CapaEffectiveness | null;
  effectiveness_note: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
  closed_by_name: string | null;
  closed_at: string | null;
  created_by_name: string | null;
  created_at: string;
  actions: CapaActionItem[];
}

export interface NcDetail {
  id: string;
  nc_code: string;
  title: string;
  description: string;
  source_type: NcSource;
  source_label: string;
  source_id: string | null;
  severity: NcSeverity;
  status: NcStatus;
  impact_assessment: string | null;
  affected_ref_type: string | null;
  affected_ref_id: string | null;
  department_id: string | null;
  department_name: string | null;
  raised_by: string;
  raised_by_name: string | null;
  raised_at: string;
  updated_at: string;
  capa: CapaDetail | null;
  warning?: string | null;
}

export interface NcStats {
  total: number;
  by_status: Partial<Record<NcStatus, number>>;
  by_severity: Partial<Record<NcSeverity, number>>;
  by_source: Partial<Record<NcSource, number>>;
  open_capa: number;
}

// ── M10: Rủi ro & Cơ hội + Cải tiến (§8.5/§8.6) ─────────────────
export type RiskKind = 'risk' | 'opportunity';
export const RISK_KIND_LABELS: Record<RiskKind, string> = {
  risk: 'Rủi ro',
  opportunity: 'Cơ hội',
};

export type RiskStatus = 'open' | 'treating' | 'monitoring' | 'closed';
export const RISK_STATUS_LABELS: Record<RiskStatus, string> = {
  open: 'Mới mở',
  treating: 'Đang xử lý',
  monitoring: 'Theo dõi',
  closed: 'Đã đóng',
};

export type RiskBand = 'low' | 'medium' | 'high';
export const RISK_BAND_LABELS: Record<RiskBand, string> = {
  low: 'Thấp',
  medium: 'Trung bình',
  high: 'Cao',
};

export type TreatmentStatus = 'todo' | 'done';

export interface RiskTreatmentItem {
  id: string;
  treatment: string;
  owner_id: string | null;
  owner_name: string | null;
  due_date: string | null;
  status: TreatmentStatus;
  done_at: string | null;
  created_at: string;
}

export interface RiskListItem {
  id: string;
  risk_code: string;
  kind: RiskKind;
  title: string;
  likelihood: number;
  impact: number;
  level: number;
  band: RiskBand;
  status: RiskStatus;
  department_id: string | null;
  department_name: string | null;
  owner_name: string | null;
  next_review_date: string | null;
  created_at: string;
}

export interface RiskDetail extends RiskListItem {
  context: string;
  process_ref: string | null;
  owner_id: string;
  closed_at: string | null;
  closed_by_name: string | null;
  updated_at: string;
  treatments: RiskTreatmentItem[];
}

export interface RiskStats {
  matrix: number[][]; // matrix[likelihood][impact], index 0..5
  by_status: Partial<Record<RiskStatus, number>>;
  by_band: Record<RiskBand, number>;
  total: number;
  open_high: number;
}

export type ImprovementSource = 'customer' | 'staff' | 'review' | 'audit' | 'other';
export const IMPROVEMENT_SOURCE_LABELS: Record<ImprovementSource, string> = {
  customer: 'Khách hàng',
  staff: 'Nhân sự',
  review: 'Xem xét lãnh đạo',
  audit: 'Đánh giá nội bộ',
  other: 'Khác',
};

export type ImprovementStatus = 'open' | 'in_progress' | 'done' | 'rejected';
export const IMPROVEMENT_STATUS_LABELS: Record<ImprovementStatus, string> = {
  open: 'Mới ghi nhận',
  in_progress: 'Đang triển khai',
  done: 'Hoàn thành',
  rejected: 'Không áp dụng',
};

export interface ImprovementItem {
  id: string;
  improvement_code: string;
  source: ImprovementSource;
  title: string;
  description: string;
  owner_id: string | null;
  owner_name: string | null;
  department_id: string | null;
  department_name: string | null;
  status: ImprovementStatus;
  linked_nc_id: string | null;
  created_at: string;
  updated_at: string;
}

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
  teaching?: Array<{ id: string; course_name: string; hk1_theory_hours: number | null; hk1_practice_hours: number | null; hk2_theory_hours: number | null; hk2_practice_hours: number | null }>;
  projects?: Array<{ id: string; title: string; level: string | null; status: string; budget_amount: string | null }>;
  publications?: Array<{ id: string; title: string; type: string; pub_scope: string | null; journal: string | null; year: number | null; is_scie: boolean; is_scopus: boolean }>;
  contracts?: Array<{ id: string; title: string; contract_type: string | null; value_amount: string | null }>;
  activities?: Array<{ id: string; kind: string; content: string }>;
}
