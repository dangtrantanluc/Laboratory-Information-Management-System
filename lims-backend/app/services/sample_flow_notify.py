"""Thông báo của luồng Nhận & Chuyển mẫu — AI được báo khi mẫu đi và về.

TÁCH RA VÌ ĐÂY LÀ RANH GIỚI THẬT, KHÔNG PHẢI ĐỂ LÁCH TRẦN DÒNG
`sample_flow_service` trả lời "mẫu đi tới đâu"; file này trả lời "ai cần biết".
Hai câu hỏi đổi vì lý do khác nhau: quy tắc định tuyến mẫu đổi khi nghiệp vụ đổi,
còn danh sách người nhận đổi khi cơ cấu tổ chức đổi (có/không có trưởng phòng,
thành viên nghỉ việc).

Quy ước chung cho mọi hàm ở đây: KHÔNG commit, KHÔNG flush. Chúng chạy trong cùng
giao dịch với thao tác nghiệp vụ gọi chúng — chuyển mẫu thất bại thì thông báo
cũng phải biến mất, không để phòng lab thấy việc không tồn tại.
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.sample_flow import DISPATCH_STATUS_LABELS, SampleDispatch, SampleIntake
from app.models.user import User
from app.services import notification_service


def lab_targets(db: Session, dept_id: uuid.UUID) -> list[uuid.UUID]:
    """Người nhận thông báo của phòng: ưu tiên trưởng phòng, không có thì mọi thành viên.

    Chỉ lấy tài khoản `active`: báo cho người đã nghỉ việc là thông báo rơi vào hư không,
    và tệ hơn là làm người còn lại tưởng đã có người nhận việc.
    """
    dept = db.get(Department, dept_id)
    if dept and dept.lead_user_id:
        return [dept.lead_user_id]
    return db.execute(
        select(User.id).where(User.department_id == dept_id, User.status == "active")
    ).scalars().all()


def notify_lab(
    db: Session, dept_id: uuid.UUID, intake: SampleIntake, dispatch: SampleDispatch
) -> None:
    """Báo phòng lab có mẫu mới được chuyển tới."""
    for uid in lab_targets(db, dept_id):
        notification_service.create_notification(
            db, user_id=uid, type="SAMPLE_DISPATCHED",
            title="Mẫu mới được chuyển đến phòng",
            body=f"{intake.code} · chỉ tiêu: {dispatch.chi_tieu[:120]}",
            ref_type="sample_dispatch", ref_id=dispatch.id,
        )


def notify_lab_batch(
    db: Session, dept_id: uuid.UUID, intake: SampleIntake, dispatches: list[SampleDispatch]
) -> None:
    """Gộp 1 thông báo cho nhiều chỉ tiêu cùng chuyển tới 1 phòng.

    Chọn 10 chỉ tiêu cùng phòng phải ra 1 thông báo, không phải 10 — chuông báo 10
    lần cho một thao tác là cách nhanh nhất khiến người dùng tắt thông báo.
    """
    if len(dispatches) == 1:
        notify_lab(db, dept_id, intake, dispatches[0])
        return
    names = ", ".join(d.chi_tieu for d in dispatches)[:200]
    for uid in lab_targets(db, dept_id):
        notification_service.create_notification(
            db, user_id=uid, type="SAMPLE_DISPATCHED",
            title=f"{len(dispatches)} chỉ tiêu mới được chuyển đến phòng",
            body=f"{intake.code} · {names}",
            ref_type="sample_dispatch", ref_id=dispatches[0].id,
        )


def notify_reception_status(
    db: Session, d: SampleDispatch, it: Optional[SampleIntake], new_status: str,
    actor_id: uuid.UUID, dept_name: Optional[str],
) -> None:
    """Báo lại phòng nhận mẫu khi phòng lab đổi trạng thái thực hiện.

    `dept_name` truyền vào chứ không tra ở đây: người gọi đã có sẵn, và nhận tham số
    giữ module này không phụ thuộc ngược vào sample_flow_service.
    """
    if it is None:
        return
    label = DISPATCH_STATUS_LABELS.get(new_status, new_status).lower()
    # set(): created_by và received_by thường là cùng một người — không báo hai lần.
    for uid in {it.created_by, it.received_by}:
        if uid and uid != actor_id:
            notification_service.create_notification(
                db, user_id=uid, type="DISPATCH_STATUS",
                title="Cập nhật trạng thái chuyển mẫu",
                body=f"{it.code} — {dept_name}: {label}",
                ref_type="sample_dispatch", ref_id=d.id,
            )
