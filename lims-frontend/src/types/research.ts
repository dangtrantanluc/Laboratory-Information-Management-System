/**
 * Kiểu dữ liệu NCKH & hoạt động — tách khỏi types/index.ts ở m34.
 *
 * index.ts chạm trần chuyển tiếp khi thêm các trường map file Excel hoạt động
 * 2024-2025. Cắt theo khối "M4: NCKH" và "Menu mới (m23)" vốn đã liền mạch sẵn,
 * không phải cắt cho vừa số dòng. Thẻ vào PTN (LabAccessCard) ở lại index.ts vì
 * thuộc M19, không thuộc nhóm này.
 *
 * index.ts re-export toàn bộ nên mọi `from '@/types'` sẵn có giữ nguyên.
 */
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
  /** Cột "Link minh chứng" của file Excel — URL ngoài, khác đính kèm tệp. */
  evidence_url?: string | null;
  status: string;
  member_count?: number;
  members?: ProjectMember[];
}

export type PublicationType = 'paper' | 'patent' | 'conference';
export type PubScope = 'domestic' | 'international';
export type PatentKind = 'invention' | 'utility_solution' | 'plant_variety';
export type TrainingLevel = 'undergraduate' | 'postgraduate';
export type CertKind = 'short_course' | 'lab_safety';

// Mỗi union đi kèm MỘT bảng nhãn ngay cạnh nó — quy ước sẵn có của tệp này
// (PUBLICATION_TYPE_LABELS, AUTHOR_ROLE_LABELS…). Kiểu Record<Union, string> chứ
// không phải Record<string, string>: thêm nhánh mới vào union mà quên nhãn thì
// TypeScript báo lỗi, thay vì để mã thô lọt ra giao diện.
export const PATENT_KIND_LABELS: Record<PatentKind, string> = {
  invention: 'Sáng chế',
  utility_solution: 'Giải pháp hữu ích',
  plant_variety: 'Giống cây trồng',
};

export const TRAINING_LEVEL_LABELS: Record<TrainingLevel, string> = {
  undergraduate: 'Đại học',
  postgraduate: 'Sau đại học',
};

export const CERT_KIND_LABELS: Record<CertKind, string> = {
  short_course: 'Lớp ngắn hạn',
  lab_safety: 'Tập huấn an toàn PTN & PCCC',
};
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
  /** Mục I/II/III của bảng sáng chế: sáng chế | giải pháp hữu ích | giống cây trồng. */
  patent_kind?: PatentKind | null;
  evidence_url?: string | null;
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

export interface TeachingCourse {
  id: string;
  user_id: string | null;
  user_name?: string | null;
  lecturer_external_name?: string | null;
  course_name: string;
  semester: string | null;
  year: number;
  academic_year?: string | null;
  /** Hai bảng riêng của sheet ĐÀO TẠO: Đại học và Sau đại học. */
  training_level?: TrainingLevel | null;
  hk1_theory_hours?: number | null;
  hk1_practice_hours?: number | null;
  hk2_theory_hours?: number | null;
  hk2_practice_hours?: number | null;
  hk3_theory_hours?: number | null;
  hk3_practice_hours?: number | null;
  note?: string | null;
  evidence_url?: string | null;
  department_id?: string | null;
  department_name?: string | null;
}

// ── Menu mới (migration m23) ─────────────────────────────────────
export interface ResearchContract {
  id: string;
  title: string;
  contract_type: string | null;
  /** Excel gộp "PUR.2024.00618 ký ngày 23/9/2024" — tách số hiệu và ngày ký. */
  contract_no?: string | null;
  signed_date?: string | null;
  value_amount: string | null;
  currency: string | null;
  partner_org: string | null;
  start_date: string | null;
  end_date: string | null;
  academic_year: string | null;
  evidence_url?: string | null;
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
  evidence_url?: string | null;
  performer_user_id: string | null;
  performer_name?: string | null;
  department_id: string | null;
  created_at?: string;
}

export interface TrainingCertificate {
  id: string;
  recipient_name: string;
  certificate_no: string | null;
  /** Hai danh sách của sheet PHỤC VỤ CỘNG ĐỒNG: lớp ngắn hạn | tập huấn an toàn PTN. */
  cert_kind?: CertKind | null;
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
  evidence_url?: string | null;
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
