/**
 * Kiểu dữ liệu KHÁCH HÀNG (M7).
 *
 * Tách khỏi types/index.ts vì file đó đã chạm trần kích thước (xem
 * scripts/check-file-size.mjs — trần chỉ được HẠ, không được nới). Khách hàng là
 * một domain khép kín nên là ranh giới tách tự nhiên; index.ts re-export lại để
 * ~40 chỗ đang `import { Customer } from '@/types'` không phải sửa.
 */

// Phải khớp CHECK constraint ck_customer_type ở DB và Literal CustomerType ở
// schemas/customer.py. 'company' từng có ở đây nhưng KHÔNG có ở hai nơi kia →
// mọi lần lưu đều 422; đã bỏ.
export type CustomerType = 'individual' | 'internal' | 'external' | 'organization';

export const CUSTOMER_TYPE_LABELS: Record<string, string> = {
  organization: 'Tổ chức / Công ty',
  individual: 'Cá nhân',
  internal: 'Nội bộ',
  external: 'Bên ngoài',
};

export interface Customer {
  id: string;
  name: string;
  type: string;
  note?: string | null;
  /** m32 — dùng để tự điền phiếu nhận mẫu BM 7.1.01 khi chọn khách từ sổ. */
  address?: string | null;
  tax_code?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  created_at?: string;
}

/**
 * m35 — một người liên hệ của khách. Danh bạ PHẲNG, không phân vai trò: nghiệp vụ
 * đã chốt là RIBE chỉ cần biết "khách này có những ai", không cần gán ai làm gì.
 */
export interface CustomerContact {
  id: string;
  customer_id: string;
  full_name: string;
  /** Chức vụ — chỉ để nhân viên nhận ra ai là ai. */
  job_title?: string | null;
  email?: string | null;
  phone?: string | null;
  /** Đúng 1 dòng/khách. Quầy nhận mẫu tự điền dòng này nên không phải bấm chọn. */
  is_primary: boolean;
  /** Nghỉ việc thì tắt, KHÔNG xoá — phiếu cũ đã in tên họ. */
  is_active: boolean;
  note?: string | null;
  created_at?: string;
}
