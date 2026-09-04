"""CRON-10 — báo giá quá hạn hiệu lực thì tự chuyển 'expired' (m41).

VÌ SAO CẦN
Mẫu báo giá của Viện ghi "có giá trị trong vòng 1 tháng", và `valid_until` được đặt
mặc định +30 ngày. Nhưng trạng thái `expired` chỉ đổi được BẰNG TAY, nên trên thực
tế không ai đổi: danh sách báo giá đầy bản 'Đã gửi khách' từ nửa năm trước, và không
phân biệt được cái nào còn hiệu lực để bám theo.

CHỈ ĐỤNG BẢN 'sent'. Bản nháp chưa gửi ai thì hết hạn không có nghĩa; bản đã
accepted/rejected đã có kết cục rồi. Cũng bỏ qua bản đã thu hồi (deleted_at).

Idempotent: chạy lại nhiều lần trong ngày không đổi thêm gì, vì sau lượt đầu không
còn bản 'sent' nào quá hạn.
"""
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.services import audit_service

logger = logging.getLogger("lims.cron.quotation")


def run_quotation_expiry(db: Session) -> dict:
    """Chuyển mọi báo giá 'sent' đã quá `valid_until` sang 'expired'.

    Session do scheduler mở và đóng (xem app/scheduler._run_tracked) — cùng quy ước
    với các cron service khác trong dự án.
    """
    session = db
    today = date.today()
    rows = session.execute(
        select(Quotation).where(
            Quotation.status == "sent",
            Quotation.deleted_at.is_(None),
            Quotation.valid_until.isnot(None),
            Quotation.valid_until < today,
        )
    ).scalars().all()

    for q in rows:
        q.status = "expired"
        # user_id=None: hệ thống làm, không phải người. Nhật ký vẫn phải có vết
        # vì đây là thay đổi trạng thái của một chứng từ đã gửi khách.
        audit_service.log_action(
            session, action="QUOTATION_EXPIRED", resource="quotation",
            user_id=None, resource_id=q.id, correlation_id=None, ip=None,
            detail={"code": q.code, "valid_until": q.valid_until.isoformat()},
        )
    session.commit()
    logger.info("CRON-10 quotation-expiry done", extra={"expired": len(rows)})
    return {"expired": len(rows)}
