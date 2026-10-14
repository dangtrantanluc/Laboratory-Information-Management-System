"""Service Báo cáo mẫu phân tích theo quý — m54.

LUỒNG
    draft ──nộp──► submitted ──chốt──► locked
      ▲               │                  │
      └──── returned ◄┘ (trả lại)        │ (mở khoá, có lý do)
                ▲────────────────────────┘

- Lab (mọi tài khoản staff / lab_manager THUỘC phòng đó) nhập, sửa, xoá dòng và nộp.
  Chỉ sửa được khi báo cáo ở draft / returned — đã nộp là nằm ở tay Văn phòng.
- Văn phòng (và admin) không sửa dữ liệu của lab: chỉ trả lại kèm lý do, chốt, hoặc
  mở khoá kèm lý do. Sửa hộ thì lab không biết số của mình đã bị đổi.
- Mọi lần chuyển trạng thái ghi nhật ký hệ thống và thông báo cho bên kia.

RÀNG BUỘC DỮ LIỆU
- Ngày nhận mẫu phải nằm trong quý của báo cáo và không ở tương lai — quý được tính
  theo ngày nhận, nên đây là thứ duy nhất giữ cho số liệu hai quý không chồng lên nhau.
- Mã mẫu KHÔNG unique: một mẫu có thể chia chỉ tiêu cho nhiều phòng.
- Chỉ tiêu: chọn từ danh mục (cùng loại mẫu) và/hoặc ghi thêm chỉ tiêu ngoài danh mục;
  phải có ít nhất một.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, conflict, forbidden, not_found
from app.core.rbac import find_permission
from app.models.department import Department
from app.models.sample_flow import MATRIX_LABELS, TestParameter
from app.models.quarterly_sample_report import (
    EDITABLE_STATUS, REPORT_STATUS_LABELS, QuarterlyReport, QuarterlyReportItem,
    QuarterlyReportItemCriterion,
)
from app.models.user import User
from app.services import audit_service, notification_service

_RESOURCE = "quarterly_sample_report"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


# ── Thời gian ─────────────────────────────────────────────────────
def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start = date(year, 3 * (quarter - 1) + 1, 1)
    nxt = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
    return start, nxt - timedelta(days=1)


def period_label(year: int, quarter: int) -> str:
    return f"Quý {ROMAN[quarter]}/{year}"


# ── Quyền ─────────────────────────────────────────────────────────
def can_review(db: Session, user: CurrentUser) -> bool:
    return find_permission(db, user.role, _RESOURCE, "review") is not None


def can_read_all(db: Session, user: CurrentUser) -> bool:
    p = find_permission(db, user.role, _RESOURCE, "read")
    return p is not None and p.scope == "all"


def lab_department(db: Session, user: CurrentUser) -> Optional[Department]:
    """Phòng lab mà user nhập liệu được — None nếu không phải thành viên lab nào."""
    if user.department_id is None or find_permission(db, user.role, _RESOURCE, "write") is None:
        return None
    dept = db.get(Department, user.department_id)
    if dept is None or dept.kind != "lab" or dept.status != "active":
        return None
    return dept


def _is_member(db: Session, user: CurrentUser, report: QuarterlyReport) -> bool:
    dept = lab_department(db, user)
    return dept is not None and dept.id == report.department_id


def _ensure_can_read(db: Session, user: CurrentUser, report: QuarterlyReport) -> None:
    if not (can_read_all(db, user) or _is_member(db, user, report)):
        raise forbidden("Bạn không xem được báo cáo của phòng khác")


def _ensure_editable(db: Session, user: CurrentUser, report: QuarterlyReport) -> None:
    if not _is_member(db, user, report):
        raise forbidden("Chỉ thành viên phòng lab này mới nhập được báo cáo")
    if report.status not in EDITABLE_STATUS:
        raise conflict(
            ErrorCode.INVALID_STATE,
            f"Báo cáo đang ở trạng thái \"{REPORT_STATUS_LABELS[report.status]}\" — không sửa được",
        )


def _ensure_reviewer(db: Session, user: CurrentUser) -> None:
    if not can_review(db, user):
        raise forbidden("Chỉ Văn phòng mới trả lại / chốt / mở khoá báo cáo")


# ── Đọc ───────────────────────────────────────────────────────────
def _user_names(db: Session, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all())


def criteria_by_item(db: Session, item_ids: list[uuid.UUID]) -> dict:
    out: dict[uuid.UUID, list[QuarterlyReportItemCriterion]] = {i: [] for i in item_ids}
    if item_ids:
        for c in db.execute(
            select(QuarterlyReportItemCriterion)
            .where(QuarterlyReportItemCriterion.item_id.in_(item_ids))
            .order_by(QuarterlyReportItemCriterion.sort_order)
        ).scalars():
            out[c.item_id].append(c)
    return out


def matrix_label(matrix: str, other: Optional[str]) -> str:
    return (other or "Khác") if matrix == "other" else MATRIX_LABELS.get(matrix, matrix)


def criteria_text(criteria: list, extra: Optional[str]) -> str:
    return ", ".join([c.name for c in criteria] + ([extra] if extra else []))


def _serialize_item(it: QuarterlyReportItem, criteria: list, names: dict) -> dict:
    return {
        "id": it.id,
        "sample_code": it.sample_code,
        "received_date": it.received_date,
        "matrix": it.matrix,
        "matrix_label": matrix_label(it.matrix, it.matrix_other),
        "matrix_other": it.matrix_other,
        "quantity": it.quantity,
        "criteria": [{"test_parameter_id": c.test_parameter_id, "name": c.name} for c in criteria],
        "extra_criteria": it.extra_criteria,
        "criteria_text": criteria_text(criteria, it.extra_criteria),
        "note": it.note,
        "created_by_name": names.get(it.created_by),
        "updated_at": it.updated_at,
    }


def load_items(db: Session, report_id: uuid.UUID) -> list[QuarterlyReportItem]:
    return list(db.execute(
        select(QuarterlyReportItem)
        .where(QuarterlyReportItem.report_id == report_id)
        .order_by(
            QuarterlyReportItem.received_date, QuarterlyReportItem.sample_code,
            QuarterlyReportItem.created_at,
        )
    ).scalars())


def _serialize(db: Session, user: CurrentUser, r: QuarterlyReport) -> dict:
    dept = db.get(Department, r.department_id)
    items = load_items(db, r.id)
    crits = criteria_by_item(db, [i.id for i in items])
    names = _user_names(
        db, [r.submitted_by, r.returned_by, r.locked_by, *(i.created_by for i in items)]
    )
    return {
        "id": r.id,
        "department_id": r.department_id,
        "department_name": dept.name,
        "department_code": dept.code,
        "year": r.year,
        "quarter": r.quarter,
        "status": r.status,
        "status_label": REPORT_STATUS_LABELS[r.status],
        "lab_note": r.lab_note,
        "submitted_by_name": names.get(r.submitted_by),
        "submitted_at": r.submitted_at,
        "returned_by_name": names.get(r.returned_by),
        "returned_at": r.returned_at,
        "return_reason": r.return_reason,
        "locked_by_name": names.get(r.locked_by),
        "locked_at": r.locked_at,
        "item_count": len(items),
        "total_quantity": sum(i.quantity for i in items),
        "items": [_serialize_item(i, crits[i.id], names) for i in items],
        "can_edit": r.status in EDITABLE_STATUS and _is_member(db, user, r),
        "can_review": can_review(db, user),
    }


def _dept_ref(d: Department) -> dict:
    return {"id": d.id, "name": d.name, "code": d.code}


def _find(db: Session, dept_id: uuid.UUID, year: int, quarter: int) -> Optional[QuarterlyReport]:
    return db.execute(
        select(QuarterlyReport).where(
            QuarterlyReport.department_id == dept_id,
            QuarterlyReport.year == year,
            QuarterlyReport.quarter == quarter,
        )
    ).scalar_one_or_none()


def get_report(db: Session, *, user: CurrentUser, report_id: uuid.UUID) -> dict:
    r = db.get(QuarterlyReport, report_id)
    if r is None:
        raise not_found("Không tìm thấy báo cáo mẫu")
    _ensure_can_read(db, user, r)
    return _serialize(db, user, r)


def get_current(
    db: Session, *, user: CurrentUser, year: int, quarter: int,
    department_id: Optional[uuid.UUID],
) -> dict:
    """Báo cáo của một phòng trong một quý (có thể chưa lập — report = None)."""
    own = lab_department(db, user)
    if department_id is None:
        if own is None:
            raise AppException(ErrorCode.VALIDATION_ERROR, "Chọn phòng lab cần xem", 422)
        dept = own
    else:
        dept = db.get(Department, department_id)
        if dept is None or dept.kind != "lab":
            raise not_found("Không tìm thấy phòng lab")
        if not can_read_all(db, user) and (own is None or own.id != dept.id):
            raise forbidden("Bạn không xem được báo cáo của phòng khác")
    r = _find(db, dept.id, year, quarter)
    is_member = own is not None and own.id == dept.id
    return {
        "department": _dept_ref(dept),
        "year": year,
        "quarter": quarter,
        "report": _serialize(db, user, r) if r else None,
        "can_edit": is_member and (r is None or r.status in EDITABLE_STATUS),
    }


def overview(db: Session, *, user: CurrentUser, year: int, quarter: int) -> list[dict]:
    """Tình trạng nộp của TẤT CẢ phòng lab trong quý — màn hình của Văn phòng."""
    if not can_read_all(db, user):
        raise forbidden()
    depts = db.execute(
        select(Department)
        .where(Department.kind == "lab", Department.status == "active")
        .order_by(Department.name)
    ).scalars().all()
    reports = {
        r.department_id: r
        for r in db.execute(
            select(QuarterlyReport).where(QuarterlyReport.year == year, QuarterlyReport.quarter == quarter)
        ).scalars()
    }
    stats = dict(
        (rid, (cnt, qty or 0))
        for rid, cnt, qty in db.execute(
            select(
                QuarterlyReportItem.report_id, func.count(), func.sum(QuarterlyReportItem.quantity)
            )
            .where(QuarterlyReportItem.report_id.in_([r.id for r in reports.values()] or [None]))
            .group_by(QuarterlyReportItem.report_id)
        ).all()
    )
    rows = []
    for d in depts:
        r = reports.get(d.id)
        cnt, qty = stats.get(r.id, (0, 0)) if r else (0, 0)
        rows.append({
            "department": _dept_ref(d),
            "report_id": r.id if r else None,
            "status": r.status if r else None,
            "status_label": REPORT_STATUS_LABELS[r.status] if r else "Chưa bắt đầu",
            "item_count": cnt,
            "total_quantity": qty,
            "submitted_at": r.submitted_at if r else None,
            "locked_at": r.locked_at if r else None,
        })
    return rows


# ── Lập báo cáo ───────────────────────────────────────────────────
def ensure_report(
    db: Session, *, user: CurrentUser, year: int, quarter: int,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Lấy (hoặc lập) báo cáo quý của phòng mình. Gọi lại nhiều lần vẫn chỉ một bản."""
    dept = lab_department(db, user)
    if dept is None:
        raise forbidden("Chỉ tài khoản thuộc phòng lab mới lập được báo cáo mẫu")
    if quarter_bounds(year, quarter)[0] > today_vn():
        raise AppException(ErrorCode.INVALID_PERIOD, "Chưa tới quý này", 422)
    r = _find(db, dept.id, year, quarter)
    if r is None:
        r = QuarterlyReport(department_id=dept.id, year=year, quarter=quarter, created_by=user.id)
        db.add(r)
        try:
            db.flush()
        except IntegrityError:
            # Hai người cùng phòng bấm cùng lúc — bản kia đã tạo, dùng lại bản đó.
            db.rollback()
            r = _find(db, dept.id, year, quarter)
        else:
            audit_service.log_action(
                db, action="QUARTERLY_SAMPLE_REPORT_CREATE", resource=_RESOURCE, user_id=user.id,
                resource_id=r.id, correlation_id=correlation_id, ip=ip,
                detail={"department": dept.code, "year": year, "quarter": quarter},
            )
            db.commit()
            db.refresh(r)
    return _serialize(db, user, r)


# ── Dòng mẫu ──────────────────────────────────────────────────────
def _lock_report(db: Session, report_id: uuid.UUID) -> QuarterlyReport:
    """Khoá hàng báo cáo trong giao dịch: lab thêm dòng cùng lúc Văn phòng bấm chốt thì
    một trong hai phải thấy trạng thái mới, không được lọt dòng vào báo cáo đã chốt."""
    r = db.execute(
        select(QuarterlyReport).where(QuarterlyReport.id == report_id).with_for_update()
    ).scalar_one_or_none()
    if r is None:
        raise not_found("Không tìm thấy báo cáo mẫu")
    return r


def _invalid(msg: str) -> AppException:
    return AppException(ErrorCode.VALIDATION_ERROR, msg, 422)


def _clean(s: Optional[str]) -> Optional[str]:
    s = " ".join((s or "").split())
    return s or None


def _load_params(db: Session, ids) -> dict:
    ids = set(ids)
    if not ids:
        return {}
    return {
        p.id: p
        for p in db.execute(select(TestParameter).where(TestParameter.id.in_(ids))).scalars()
    }


def _validate_item(
    db: Session, r: QuarterlyReport, body: dict, params_by_id: Optional[dict] = None,
) -> tuple[dict, list[TestParameter]]:
    """params_by_id: danh mục đã nạp sẵn (nhập theo lô) — tránh một truy vấn mỗi dòng."""
    start, end = quarter_bounds(r.year, r.quarter)
    received: date = body["received_date"]
    if not (start <= received <= end):
        raise _invalid(
            f"Ngày nhận mẫu phải trong {period_label(r.year, r.quarter)} "
            f"({start:%d/%m/%Y} – {end:%d/%m/%Y})"
        )
    if received > today_vn():
        raise _invalid("Ngày nhận mẫu không được ở tương lai")
    code = _clean(body["sample_code"])
    if not code:
        raise _invalid("Nhập mã số mẫu")
    matrix = body["matrix"]
    matrix_other = _clean(body.get("matrix_other")) if matrix == "other" else None
    if matrix == "other" and not matrix_other:
        raise _invalid("Loại mẫu \"Khác\" — ghi rõ loại mẫu")

    ids = list(dict.fromkeys(body.get("test_parameter_ids") or []))
    params: list[TestParameter] = []
    if ids:
        found = params_by_id if params_by_id is not None else _load_params(db, ids)
        missing = [i for i in ids if i not in found]
        if missing:
            raise _invalid("Có chỉ tiêu không còn trong danh mục — tải lại trang rồi chọn lại")
        params = [found[i] for i in ids]
        if matrix != "other":
            wrong = [p.name for p in params if p.matrix != matrix]
            if wrong:
                raise _invalid(
                    f"Chỉ tiêu không thuộc loại mẫu {MATRIX_LABELS[matrix]}: {', '.join(wrong[:3])}"
                )
    extra = (body.get("extra_criteria") or "").strip() or None
    if not params and not extra:
        raise _invalid("Chọn ít nhất một chỉ tiêu phân tích")
    data = {
        "sample_code": code,
        "received_date": received,
        "matrix": matrix,
        "matrix_other": matrix_other,
        "quantity": body["quantity"],
        "extra_criteria": extra,
        "note": (body.get("note") or "").strip() or None,
    }
    return data, params


def _write_criteria(db: Session, item_id: uuid.UUID, params: list[TestParameter]) -> None:
    db.query(QuarterlyReportItemCriterion).filter(
        QuarterlyReportItemCriterion.item_id == item_id
    ).delete(synchronize_session=False)
    for i, p in enumerate(params):
        db.add(QuarterlyReportItemCriterion(
            item_id=item_id, test_parameter_id=p.id, name=p.name, sort_order=i,
        ))


def _item_out(db: Session, it: QuarterlyReportItem) -> dict:
    crits = criteria_by_item(db, [it.id])[it.id]
    return _serialize_item(it, crits, _user_names(db, [it.created_by]))


def _touch(r: QuarterlyReport) -> None:
    r.updated_at = datetime.now(timezone.utc)


def create_item(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, body: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    r = _lock_report(db, report_id)
    _ensure_editable(db, user, r)
    data, params = _validate_item(db, r, body)
    it = QuarterlyReportItem(report_id=r.id, created_by=user.id, updated_by=user.id, **data)
    db.add(it)
    db.flush()
    _write_criteria(db, it.id, params)
    _touch(r)
    audit_service.log_action(
        db, action="QUARTERLY_SAMPLE_REPORT_ITEM_CREATE", resource=_RESOURCE, user_id=user.id,
        resource_id=r.id, correlation_id=correlation_id, ip=ip,
        detail={"item_id": str(it.id), "sample_code": it.sample_code},
    )
    db.commit()
    db.refresh(it)
    return _item_out(db, it)


BATCH_MAX = 500


def create_items_batch(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, items: list[dict],
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Nhập nhiều mẫu một lần — TẤT CẢ hoặc KHÔNG dòng nào.

    Lưu một nửa lô rồi báo lỗi nửa còn lại buộc người nhập phải dò xem dòng nào đã vào,
    dòng nào chưa; dễ nhập trùng khi bấm lưu lại. Nên có dòng lỗi là không lưu gì, và
    trả về lỗi theo từng dòng (details[].row, đánh số từ 1) để giao diện tô đúng dòng.
    """
    r = _lock_report(db, report_id)
    _ensure_editable(db, user, r)
    params_by_id = _load_params(
        db, (pid for body in items for pid in body.get("test_parameter_ids") or [])
    )
    validated, errors = [], []
    for i, body in enumerate(items, start=1):
        try:
            validated.append(_validate_item(db, r, body, params_by_id))
        except AppException as e:
            errors.append({"row": i, "sample_code": _clean(body.get("sample_code")), "message": e.message})
    if errors:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            f"{len(errors)}/{len(items)} dòng chưa hợp lệ — chưa lưu dòng nào",
            422,
            details=errors,
        )
    for data, params in validated:
        it = QuarterlyReportItem(report_id=r.id, created_by=user.id, updated_by=user.id, **data)
        db.add(it)
        db.flush()
        _write_criteria(db, it.id, params)
    _touch(r)
    codes = [d["sample_code"] for d, _ in validated]
    audit_service.log_action(
        db, action="QUARTERLY_SAMPLE_REPORT_ITEM_BATCH_CREATE", resource=_RESOURCE,
        user_id=user.id, resource_id=r.id, correlation_id=correlation_id, ip=ip,
        detail={"count": len(codes), "sample_codes": codes[:100]},
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, user, r)


def update_item(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, item_id: uuid.UUID, body: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    r = _lock_report(db, report_id)
    _ensure_editable(db, user, r)
    it = db.get(QuarterlyReportItem, item_id)
    if it is None or it.report_id != r.id:
        raise not_found("Không tìm thấy dòng mẫu")
    data, params = _validate_item(db, r, body)
    for k, v in data.items():
        setattr(it, k, v)
    it.updated_by = user.id
    it.updated_at = datetime.now(timezone.utc)
    _write_criteria(db, it.id, params)
    _touch(r)
    audit_service.log_action(
        db, action="QUARTERLY_SAMPLE_REPORT_ITEM_UPDATE", resource=_RESOURCE, user_id=user.id,
        resource_id=r.id, correlation_id=correlation_id, ip=ip,
        detail={"item_id": str(it.id), "sample_code": it.sample_code},
    )
    db.commit()
    db.refresh(it)
    return _item_out(db, it)


def delete_item(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, item_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    r = _lock_report(db, report_id)
    _ensure_editable(db, user, r)
    it = db.get(QuarterlyReportItem, item_id)
    if it is None or it.report_id != r.id:
        raise not_found("Không tìm thấy dòng mẫu")
    code = it.sample_code
    db.delete(it)
    _touch(r)
    audit_service.log_action(
        db, action="QUARTERLY_SAMPLE_REPORT_ITEM_DELETE", resource=_RESOURCE, user_id=user.id,
        resource_id=r.id, correlation_id=correlation_id, ip=ip,
        detail={"item_id": str(item_id), "sample_code": code},
    )
    db.commit()


# ── Chuyển trạng thái ─────────────────────────────────────────────
def _notify(db: Session, user_ids, *, type: str, title: str, body: Optional[str], r: QuarterlyReport):
    for uid in set(user_ids):
        notification_service.create_notification(
            db, user_id=uid, type=type, title=title, body=body,
            ref_type="quarterly_sample_report", ref_id=r.id,
        )


def _office_user_ids(db: Session) -> list[uuid.UUID]:
    return list(db.execute(
        select(User.id).where(User.role == "office", User.status == "active")
    ).scalars())


def _dept_user_ids(db: Session, dept_id: uuid.UUID, exclude: uuid.UUID) -> list[uuid.UUID]:
    return [
        uid for uid in db.execute(
            select(User.id).where(User.department_id == dept_id, User.status == "active")
        ).scalars()
        if uid != exclude
    ]


def _require_status(r: QuarterlyReport, allowed: tuple[str, ...], action: str) -> None:
    if r.status not in allowed:
        raise conflict(
            ErrorCode.INVALID_STATE_TRANSITION,
            f"Không thể {action}: báo cáo đang \"{REPORT_STATUS_LABELS[r.status]}\"",
        )


def _audit(db, user, r, action, cid, ip, **detail):
    audit_service.log_action(
        db, action=action, resource=_RESOURCE, user_id=user.id, resource_id=r.id,
        correlation_id=cid, ip=ip,
        detail={"year": r.year, "quarter": r.quarter, "department_id": str(r.department_id), **detail},
    )


def submit(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, lab_note: Optional[str],
    confirm_empty: bool, correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    r = _lock_report(db, report_id)
    if not _is_member(db, user, r):
        raise forbidden("Chỉ thành viên phòng lab này mới nộp được báo cáo")
    _require_status(r, EDITABLE_STATUS, "nộp")
    count = db.execute(
        select(func.count()).select_from(QuarterlyReportItem)
        .where(QuarterlyReportItem.report_id == r.id)
    ).scalar_one()
    if count == 0 and not confirm_empty:
        raise _invalid("Báo cáo chưa có mẫu nào — xác nhận \"Không phát sinh mẫu\" nếu đúng như vậy")
    r.status = "submitted"
    r.submitted_by = user.id
    r.submitted_at = datetime.now(timezone.utc)
    r.lab_note = (lab_note or "").strip() or None
    _touch(r)
    _audit(db, user, r, "QUARTERLY_SAMPLE_REPORT_SUBMIT", correlation_id, ip, items=count)
    dept = db.get(Department, r.department_id)
    _notify(
        db, _office_user_ids(db), type="quarterly_report_submitted", r=r,
        title=f"{dept.name} đã nộp báo cáo mẫu {period_label(r.year, r.quarter)}",
        body=f"{count} dòng mẫu" if count else "Không phát sinh mẫu",
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, user, r)


def return_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, reason: str,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _ensure_reviewer(db, user)
    r = _lock_report(db, report_id)
    _require_status(r, ("submitted",), "trả lại")
    return _hand_back(db, user, r, reason, "QUARTERLY_SAMPLE_REPORT_RETURN", "bị trả lại", correlation_id, ip)


def reopen(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, reason: str,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _ensure_reviewer(db, user)
    r = _lock_report(db, report_id)
    _require_status(r, ("locked",), "mở khoá")
    return _hand_back(db, user, r, reason, "QUARTERLY_SAMPLE_REPORT_REOPEN", "được mở khoá", correlation_id, ip)


def _hand_back(db, user, r, reason, action, verb, cid, ip) -> dict:
    """Trả lại / mở khoá: báo cáo về tay lab kèm lý do, lab sửa rồi nộp lại."""
    r.status = "returned"
    r.returned_by = user.id
    r.returned_at = datetime.now(timezone.utc)
    r.return_reason = reason.strip()
    r.locked_by = None
    r.locked_at = None
    _touch(r)
    _audit(db, user, r, action, cid, ip, reason=r.return_reason)
    _notify(
        db, _dept_user_ids(db, r.department_id, user.id), type="quarterly_report_returned", r=r,
        title=f"Báo cáo mẫu {period_label(r.year, r.quarter)} {verb}",
        body=r.return_reason,
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, user, r)


def lock(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _ensure_reviewer(db, user)
    r = _lock_report(db, report_id)
    _require_status(r, ("submitted",), "chốt")
    r.status = "locked"
    r.locked_by = user.id
    r.locked_at = datetime.now(timezone.utc)
    _touch(r)
    _audit(db, user, r, "QUARTERLY_SAMPLE_REPORT_LOCK", correlation_id, ip)
    _notify(
        db, _dept_user_ids(db, r.department_id, user.id), type="quarterly_report_locked", r=r,
        title=f"Báo cáo mẫu {period_label(r.year, r.quarter)} đã được Văn phòng chốt",
        body=None,
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, user, r)
