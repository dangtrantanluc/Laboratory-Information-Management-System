"""Model test_reports (m46) — PHIẾU KẾT QUẢ THỬ NGHIỆM đã phát hành (BM 7.8/01/RIBE).

Đây là CHỨNG TỪ, không phải dữ liệu kết quả. Nội dung phiếu nằm trong tệp đính kèm
(owner_type 'test_report'); bảng này giữ những gì tệp không tự nói được: số hiệu, ngày
phát hành, người phát hành, bản sửa đổi thứ mấy và vì sao, đã gửi cho ai, đã thu hồi chưa.

NEO Ở CẤP PHIẾU NHẬN MẪU, KHÔNG PHẢI Ở LƯỢT CHUYỂN HAY MẪU M1
Header biểu mẫu ghi `Mã KH/Customer code: 26N323` — đúng bằng `sample_intakes.code`, và
tên tệp là "26N323 - <tên khách>.docx". Một tệp phủ cả bốn khối, trải cả mẫu nước lẫn mẫu
đất, tức là vượt phạm vi một `sample_dispatch` (1 chỉ tiêu → 1 phòng) và cả một `Sample`
của M1 (1 phiếu × 1 phòng). Một phiếu nhận → 0..n phiếu kết quả: nhiều hơn một khi có bản
sửa đổi, hoặc khi khách yêu cầu tách phiếu theo từng hộ (biến thể "Theo hộ" trong
docs/layout/, mà resultPdf.ts đã dựng sẵn).

BẤT BIẾN SAU KHI PHÁT HÀNH
`issued` khoá cả tệp lẫn siêu dữ liệu. Muốn đổi nội dung phải tạo BẢN GHI MỚI
(version+1, `supersedes_id` trỏ bản cũ), không viết đè — khách đang cầm bản cũ trên tay.
Bỏ ràng buộc này đi thì phần còn lại chỉ là một thư mục chia sẻ có thêm vài ô nhập.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, ForeignKey, Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_TEST_REPORT_STATUS = ("draft", "issued", "delivered", "revoked")

TEST_REPORT_STATUS_LABELS = {
    "draft": "Nháp",
    "issued": "Đã phát hành",
    "delivered": "Đã gửi khách",
    "revoked": "Đã thu hồi",
}

# Bước hợp lệ kế tiếp. `draft` KHÔNG đi thẳng sang 'revoked' được: chưa phát hành thì
# không có gì để thu hồi — bản nháp sai thì xoá (mềm), đó là thao tác khác hẳn.
# `delivered` và `revoked` là điểm dừng: sửa nội dung sau khi đã trao khách phải đi qua
# đường tạo bản sửa đổi, không phải bằng cách lùi trạng thái. Cùng bài học m37 đã rút ra
# với sample_dispatches, nơi `done → sent → sửa → done` lặp vô hạn từng là hợp lệ.
TEST_REPORT_NEXT = {
    "draft": ("issued",),
    "issued": ("delivered", "revoked"),
    "delivered": ("revoked",),
    "revoked": (),
}

# Khớp bộ giá trị `return_method` đã có trên phiếu nhận mẫu (BM 7.1.01) — nhân viên
# quầy đã ghi hình thức trả kết quả ở đó, màn hình này chỉ điền sẵn lại.
VALID_DELIVERY_METHOD = ("direct", "mail", "email")

DELIVERY_METHOD_LABELS = {
    "direct": "Trao trực tiếp",
    "mail": "Gửi bưu điện",
    "email": "Gửi email",
}


class TestReport(Base):
    __tablename__ = "test_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sample_intakes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Mặc định = mã phiếu nhận; phiếu song song thêm hậu tố -2, -3; bản sửa đổi -R1, -R2.
    # Cho sửa tay, giống cách nhân viên tự đặt mã phiếu nhận hiện nay.
    report_no: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_reports.id", ondelete="SET NULL"), nullable=True
    )
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'draft'")
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ngày in trên phiếu ("Ngày trả kết quả / Date of reporting"). Kiểu DATE chứ không
    # phải timestamp: đây là một ngày trên giấy tờ, không phải một thời điểm hệ thống.
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    delivery_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivered_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Xoá MỀM — cùng quyết định m41 đã áp cho báo giá đã gửi khách. Chỉ bản nháp mới
    # xoá được; đã phát hành thì thu hồi.
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','issued','delivered','revoked')", name="ck_tr_status"
        ),
        CheckConstraint("version >= 1", name="ck_tr_version"),
        CheckConstraint(
            "version = 1 OR (revision_reason IS NOT NULL "
            "AND length(btrim(revision_reason)) > 0)",
            name="ck_tr_revision_reason",
        ),
        CheckConstraint(
            "status = 'draft' OR (issued_at IS NOT NULL AND issued_by IS NOT NULL)",
            name="ck_tr_issued_pair",
        ),
        CheckConstraint(
            "status <> 'delivered' OR delivered_at IS NOT NULL", name="ck_tr_delivered"
        ),
        CheckConstraint(
            "status <> 'revoked' OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL "
            "AND revoked_reason IS NOT NULL AND length(btrim(revoked_reason)) > 0)",
            name="ck_tr_revoked",
        ),
        CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('direct','mail','email')",
            name="ck_tr_delivery_method",
        ),
    )
