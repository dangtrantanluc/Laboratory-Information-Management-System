import { ApiError } from './api';

/** Map error.code → message tiếng Việt rõ nghĩa cho nghiệp vụ. */
const CODE_MESSAGES: Record<string, string> = {
  // auth
  INVALID_CREDENTIALS: 'Email hoặc mật khẩu không đúng',
  ACCOUNT_LOCKED: 'Tài khoản tạm khóa do nhập sai quá nhiều lần. Vui lòng thử lại sau.',
  ACCOUNT_DISABLED: 'Tài khoản đã bị vô hiệu hóa. Liên hệ quản trị viên.',
  RATE_LIMIT_EXCEEDED: 'Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút.',
  TOKEN_INVALID: 'Phiên đăng nhập không hợp lệ, vui lòng đăng nhập lại.',
  TOKEN_EXPIRED: 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.',
  TOKEN_REUSED: 'Phát hiện dùng lại phiên cũ. Vì an toàn, vui lòng đăng nhập lại.',
  UNAUTHORIZED: 'Vui lòng đăng nhập để tiếp tục.',
  WEAK_PASSWORD: 'Mật khẩu mới quá yếu (tối thiểu 8 ký tự).',
  PASSWORD_MISMATCH: 'Mật khẩu hiện tại không đúng.',

  // RBAC
  FORBIDDEN: 'Bạn không có quyền thực hiện thao tác này.',
  FORBIDDEN_ACCOUNTANT: 'Vai trò Kế toán không được truy cập nghiệp vụ mẫu.',
  VALIDATION_ERROR: 'Dữ liệu nhập chưa hợp lệ, vui lòng kiểm tra lại.',
  NOT_FOUND: 'Không tìm thấy dữ liệu.',

  // samples
  ASSIGNEE_OUT_OF_DEPT: 'Người được giao không cùng phòng ban với mẫu.',
  ASSIGNEE_NOT_FOUND: 'Không tìm thấy người được giao.',
  INVALID_STATE_TRANSITION: 'Không thể thực hiện thao tác này ở trạng thái hiện tại.',
  NOT_CURRENT_CUSTODIAN: 'Bạn không phải người đang giữ mẫu này.',
  HANDOVER_OUT_OF_DEPT: 'Người nhận không cùng phòng ban với mẫu.',
  INVALID_HANDOVER: 'Người nhận đang là người giữ mẫu hiện tại.',
  NOT_ASSIGNEE: 'Bạn không phải người được giao phần việc này.',
  RESULT_LOCKED: 'Kết quả đã duyệt — phải tạo bản sửa đổi (revise).',
  SELF_APPROVAL_FORBIDDEN: 'Người nhập kết quả không được tự duyệt kết quả của mình.',
  NO_RESULT_TO_APPROVE: 'Phần việc chưa có kết quả để duyệt.',
  RESULT_ALREADY_APPROVED: 'Kết quả đã được duyệt.',
  RESULT_NOT_APPROVED: 'Kết quả chưa được duyệt.',
  RESULT_EXISTS: 'Phân công đã có kết quả — không thể hủy.',
  REVISION_REASON_REQUIRED: 'Cần nhập lý do khi sửa kết quả đã duyệt.',
  CONDITION_REASON_REQUIRED: 'Cần nhập lý do khi tình trạng mẫu không đạt.',
  RESULTS_NOT_APPROVED: 'Còn phần việc chưa được duyệt — không thể chốt mẫu.',
  OVERDUE_REASON_REQUIRED: 'Mẫu quá hạn cần nhập lý do trễ trước khi chốt/xuất phiếu.',
  SAMPLE_NOT_OVERDUE: 'Mẫu không ở trạng thái quá hạn.',
  SAMPLE_NOT_FINALIZED: 'Mẫu chưa được chốt hoàn thành.',
  INVALID_DEADLINE: 'Hạn mới phải lớn hơn ngày tiếp nhận.',
  CUSTOMER_NOT_FOUND: 'Không tìm thấy khách hàng.',
  RESULT_NOT_PUBLISHED: 'Kết quả chưa được công khai.',

  // chemicals
  INVALID_QUANTITY: 'Số lượng phải lớn hơn 0.',
  REASON_REQUIRED: 'Cần nhập lý do cho giao dịch điều chỉnh.',
  INVALID_UNIT: 'Đơn vị không hợp lệ.',
  UNIT_GROUP_MISMATCH: 'Đơn vị khác nhóm đo với đơn vị cơ sở.',
  UNIT_LOCKED: 'Không thể đổi đơn vị cơ sở khi đã có lô/giao dịch.',
  SAMPLE_REQUIRED: 'Xuất hóa chất phải gắn với một mẫu.',
  SAMPLE_NOT_FOUND: 'Mẫu tham chiếu không tồn tại.',
  INSUFFICIENT_STOCK: 'Tồn kho không đủ để xuất.',
  WARNING_NEEDS_CONFIRM: 'Lô có cảnh báo — cần xác nhận để tiếp tục.',
  NEGATIVE_BALANCE: 'Điều chỉnh khiến tồn kho âm.',
  INVALID_DATE_ORDER: 'Ngày kết thúc phải sau ngày bắt đầu.',
  DUPLICATE_CUSTOMER: 'Khách hàng đã tồn tại.',

  // M4 — Nhân sự & NCKH
  SALARY_FORBIDDEN: 'Bạn không có quyền xem/sửa lương. Chỉ Kế toán và Quản trị viên được điều chỉnh lương.',
  PROFILE_NOT_FOUND: 'Không tìm thấy hồ sơ nhân sự.',
  DUPLICATE_PROFILE: 'Người dùng này đã có hồ sơ nhân sự.',
  HR_PROFILE_EXISTS: 'Người dùng này đã có hồ sơ nhân sự.',
  USER_NOT_FOUND: 'Không tìm thấy người dùng.',
  INVALID_CONTRACT_TYPE: 'Loại hợp đồng không hợp lệ.',
  INVALID_CYCLE: 'Chu kỳ nâng lương phải là số nguyên ≥ 1.',
  INVALID_SALARY: 'Hệ số và lương cơ sở phải lớn hơn 0.',
  FUTURE_RAISE_NOT_ALLOWED: 'Ngày nâng lương không được ở tương lai.',
  COMPETENCE_NOT_FOUND: 'Không tìm thấy mục năng lực.',
  INVALID_FILE_TYPE: 'Định dạng tệp không hợp lệ (PDF, PNG, JPEG).',
  FILE_TOO_LARGE: 'Tệp vượt quá dung lượng cho phép (20MB).',
  PROJECT_NOT_FOUND: 'Không tìm thấy đề tài.',
  LEAD_REQUIRED: 'Phải có chủ nhiệm và chủ nhiệm phải nằm trong danh sách thành viên.',
  INVALID_PROJECT_LEVEL: 'Cấp đề tài không hợp lệ.',
  DUPLICATE_MEMBER: 'Một thành viên xuất hiện nhiều lần trong đề tài.',
  INVALID_AUTHOR:
    'Mỗi tác giả/thành viên phải là người nội bộ HOẶC tên người ngoài hệ thống, không được cả hai hay bỏ trống.',
  PUBLICATION_NOT_FOUND: 'Không tìm thấy bài báo/sáng chế.',
  INVALID_INDEX: 'Chỉ số bài báo không hợp lệ.',
  DUPLICATE_AUTHOR_ORDER: 'Thứ tự tác giả bị trùng trong cùng một bài.',
  DUPLICATE_PATENT_NO: 'Số bằng sáng chế đã tồn tại.',
  MENTORSHIP_NOT_FOUND: 'Không tìm thấy bản ghi hướng dẫn sinh viên.',
  INVALID_MENTORSHIP_TYPE: 'Loại hướng dẫn không hợp lệ.',
  REGISTRATION_NOT_FOUND: 'Không tìm thấy lượt đăng ký lab.',
  REGISTRATION_ALREADY_DECIDED: 'Lượt đăng ký đã được duyệt/từ chối — không thể quyết lại.',
  TEACHING_COURSE_NOT_FOUND: 'Không tìm thấy môn giảng dạy.',
  DUPLICATE_COURSE: 'Trùng môn giảng dạy (người + môn + kỳ + năm).',
  COMMUNITY_SERVICE_NOT_FOUND: 'Không tìm thấy hoạt động cộng đồng.',
  INVALID_DATE_RANGE: 'Khoảng thời gian không hợp lệ (từ ngày phải trước đến ngày).',

  // ── M3 — Quản lý tài liệu ──
  DOCUMENT_NOT_FOUND: 'Không tìm thấy tài liệu (hoặc bạn không có quyền truy cập).',
  VERSION_NOT_FOUND: 'Không tìm thấy phiên bản tài liệu.',
  DEPARTMENT_NOT_FOUND: 'Không tìm thấy phòng ban.',
  DUPLICATE_DOCUMENT_CODE: 'Không sinh được mã tài liệu duy nhất, vui lòng thử lại.',
  DRAFT_ALREADY_EXISTS: 'Tài liệu đang có một phiên bản nháp/chờ duyệt — hãy hoàn tất phiên bản đó trước.',
  VERSION_CONFLICT: 'Một phiên bản khác vừa được ban hành. Vui lòng tải lại và thử lại.',
  CHANGE_NOTE_REQUIRED: 'Bắt buộc nhập ghi chú thay đổi từ phiên bản thứ 2 trở đi.',
  REJECT_REASON_REQUIRED: 'Vui lòng nhập lý do từ chối.',
  VERSION_NOT_PUBLISHED: 'Phiên bản chưa được ban hành — bạn không có quyền xem/tải.',
  RESTRICTED_ACCESS: 'Tài liệu hạn chế — chỉ phòng sở hữu và Ban lãnh đạo được truy cập.',
  OBSOLETE_DOWNLOAD_FORBIDDEN: 'Không thể tải phiên bản đã lỗi thời.',
  VERSION_LOCKED: 'Chỉ sửa được phiên bản đang ở trạng thái nháp.',
  // SELF_APPROVAL_FORBIDDEN & INVALID_STATE_TRANSITION đã định nghĩa ở mục mẫu — dùng chung.
  VERSION_FILE_REQUIRED: 'Phiên bản chưa có tệp đính kèm — không thể gửi duyệt.',
  CODE_IMMUTABLE: 'Mã tài liệu không thể thay đổi sau khi tạo.',
  DOCUMENT_HAS_APPROVED_VERSION: 'Tài liệu đã có phiên bản ban hành — không thể xóa (giữ hồ sơ §8.4).',
  INVALID_DOC_TYPE: 'Loại tài liệu không hợp lệ.',
  INVALID_CONFIDENTIALITY: 'Mức bảo mật không hợp lệ.',
  STORAGE_UNAVAILABLE: 'Hệ thống lưu trữ tệp tạm thời không khả dụng, vui lòng thử lại.',
  // INVALID_FILE_TYPE & FILE_TOO_LARGE đã định nghĩa ở mục M4 — dùng chung.

  // ── M5 — Thiết bị & Hiệu chuẩn ──
  EQUIPMENT_NOT_FOUND: 'Không tìm thấy thiết bị (hoặc đã ngưng sử dụng).',
  DUPLICATE_EQUIPMENT_CODE: 'Không sinh được mã thiết bị duy nhất, vui lòng thử lại.',
  INVALID_STATUS: 'Tình trạng thiết bị không hợp lệ.',
  INVALID_CALIBRATION_CYCLE:
    'Chu kỳ hiệu chuẩn không hợp lệ — phải nhập đủ cả số và đơn vị, số > 0.',
  CALIBRATION_CYCLE_REQUIRED:
    'Thiết bị chưa cấu hình chu kỳ hiệu chuẩn. Hãy đặt chu kỳ hoặc nhập ngày kế tiếp thủ công.',
  CALIBRATION_CERT_REQUIRED: 'Cần đính kèm giấy chứng nhận (CoC) khi kết quả Đạt.',
  INVALID_CALIBRATION_DATE: 'Ngày hiệu chuẩn không được ở tương lai.',
  INVALID_CALIBRATION_RESULT: 'Kết quả hiệu chuẩn không hợp lệ (Đạt / Không đạt).',
  OVERRIDE_REASON_REQUIRED: 'Cần nhập lý do khi ghi đè ngày hiệu chuẩn kế tiếp.',
  RESPONSIBLE_NOT_IN_DEPARTMENT: 'Người phụ trách phải cùng phòng ban với thiết bị.',
  CALIBRATION_NOT_FOUND: 'Không tìm thấy bản ghi hiệu chuẩn.',
  CERT_NOT_FOUND: 'Bản ghi hiệu chuẩn này không có giấy chứng nhận đính kèm.',
  ATTACHMENT_NOT_FOUND: 'Không tìm thấy tệp đính kèm.',
  CRON_ALREADY_RUNNING: 'Tác vụ nhắc hiệu chuẩn đang chạy, vui lòng thử lại sau.',

  // ── M6 — Báo cáo & Dashboard ──
  INVALID_DATE_RANGE_REPORT: 'Khoảng thời gian không hợp lệ (từ ngày phải trước đến ngày).',
  INVALID_GROUP_BY: 'Đơn vị thời gian không hợp lệ (chọn ngày / tuần / tháng).',
  REPORT_TYPE_NOT_FOUND: 'Loại báo cáo không được hỗ trợ.',
  PDF_NOT_SUPPORTED: 'Báo cáo này chưa hỗ trợ xuất PDF. Vui lòng dùng định dạng Excel.',
  EXPORT_RANGE_TOO_LARGE: 'Khoảng thời gian quá rộng để xuất trực tiếp — vui lòng thu hẹp kỳ báo cáo.',
  // FORBIDDEN, VALIDATION_ERROR, DEPARTMENT_NOT_FOUND, USER_NOT_FOUND, CHEMICAL_NOT_FOUND,
  // STORAGE_UNAVAILABLE, RATE_LIMIT_EXCEEDED, UNAUTHORIZED đã định nghĩa ở trên — dùng chung.
  // CODE_IMMUTABLE, INVALID_DATE_ORDER, DEPARTMENT_NOT_FOUND, USER_NOT_FOUND,
  // INVALID_FILE_TYPE, FILE_TOO_LARGE, STORAGE_UNAVAILABLE đã định nghĩa ở trên — dùng chung.
};

/** Trả message tiếng Việt cho lỗi. Lỗi kỹ thuật (5xx) ẩn chi tiết + kèm correlationId. */
export function describeError(err: unknown): { title: string; description?: string } {
  if (err instanceof ApiError) {
    if (err.status >= 500) {
      const cid = err.correlationId ? ` (mã lỗi ${err.correlationId.slice(0, 8)})` : '';
      return { title: 'Lỗi hệ thống, vui lòng thử lại' + cid };
    }
    const msg = CODE_MESSAGES[err.code] ?? err.message ?? 'Đã xảy ra lỗi';
    return { title: msg };
  }
  if (err instanceof Error) return { title: err.message };
  return { title: 'Đã xảy ra lỗi không xác định' };
}

export { ApiError };
