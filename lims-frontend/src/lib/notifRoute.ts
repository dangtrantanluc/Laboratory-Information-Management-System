import type { Notification } from '@/types';

/**
 * Bản đồ điều hướng khi click 1 thông báo → mở đúng trang/nội dung liên quan.
 * Trả null nếu không có đích (chỉ đánh dấu đã đọc).
 */
export function notifTarget(n: Notification): string | null {
  const id = n.ref_id;
  switch (n.ref_type) {
    case 'sample':
      return id ? `/samples/sample/${id}` : '/samples';
    // Nhận & Chuyển mẫu (GĐ2b) — mở trang, vai trò tự vào tab phù hợp; focus phiếu chuyển
    case 'sample_dispatch':
      return id ? `/sample-flow?focus=${id}` : '/sample-flow';
    case 'sample_intake':
      return id ? `/sample-flow?intake=${id}` : '/sample-flow';
    // Kho biểu mẫu VILAS — minh chứng
    case 'form_submission':
      return '/forms?tab=submissions';
    case 'equipment':
      return id ? `/equipment/${id}` : '/equipment';
    case 'chemical':
      return id ? `/chemicals/${id}` : '/chemicals';
    case 'document':
    case 'document_version':
      return id ? `/documents/${id}` : '/documents';
    case 'hr_profile':
      return id ? `/hr/${id}` : '/hr';
    case 'nonconformity':
      return '/nonconformities';
    case 'risk':
      return '/risks';
    default:
      return null;
  }
}
