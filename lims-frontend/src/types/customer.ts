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
  contact: string | null;
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
