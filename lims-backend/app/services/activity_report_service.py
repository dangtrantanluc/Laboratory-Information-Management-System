"""Service báo cáo hoạt động hàng tháng (m25).

Giảng viên/leader/lãnh đạo/KTV nộp báo cáo 1 kỳ (tháng) gồm các dòng hoạt động. Mỗi dòng
được tạo THẲNG vào bảng thành tích đã có (gắn report_id + gắn người nộp) → tự hiện ở module
tương ứng (Đề tài/Bài báo/Hợp đồng/Giảng dạy/Công tác khác). Văn phòng xem danh sách + duyệt.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.hr import (
    ActivityReport,
    Publication,
    PublicationAuthor,
    ProjectMember,
    ResearchContract,
    ResearchProject,
    StaffActivity,
    TeachingCourse,
)
from app.services import audit_service, hr_common as hc

# Ai được NỘP báo cáo (người thực hiện chuyên môn). Văn phòng KHÔNG nộp — chỉ tổng hợp/duyệt.
_REPORTER_ROLES = ("admin", "leader", "lab_manager", "staff")
# Ai xem TẤT CẢ báo cáo + duyệt (tổng hợp).
_REVIEWER_ROLES = ("admin", "leader", "office")


def _assert_reporter(user: CurrentUser) -> None:
    if user.role not in _REPORTER_ROLES:
        raise hc.forbidden("Vai trò của bạn không nộp báo cáo hoạt động")


def _can_review(user: CurrentUser) -> bool:
    return user.role in _REVIEWER_ROLES


def _parse_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


# ===================== CREATE =====================
def create_report(db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip) -> dict:
    _assert_reporter(user)
    period = str(payload.get("period_label") or "").strip()
    if not period:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu kỳ báo cáo (period_label)", 400)

    dept_id = payload.get("department_id") or user.department_id
    academic_year = payload.get("academic_year")

    rep = ActivityReport(
        reporter_user_id=user.id, department_id=dept_id, period_label=period,
        period_year=_parse_int(payload.get("period_year")), academic_year=academic_year,
        status="submitted", note=payload.get("note"),
        submitted_at=datetime.now(timezone.utc), created_by=user.id,
    )
    db.add(rep)
    try:
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()
        raise AppException(ErrorCode.DUPLICATE_REPORT, f"Bạn đã có báo cáo kỳ '{period}'", 409)

    # ---- Giảng dạy ----
    for t in payload.get("teaching") or []:
        if not t.get("course_name"):
            continue
        db.add(TeachingCourse(
            user_id=user.id, course_name=str(t["course_name"]).strip(),
            semester=t.get("semester"), academic_year=academic_year, report_id=rep.id,
            hk1_theory_hours=_parse_int(t.get("hk1_theory_hours")),
            hk1_practice_hours=_parse_int(t.get("hk1_practice_hours")),
            hk2_theory_hours=_parse_int(t.get("hk2_theory_hours")),
            hk2_practice_hours=_parse_int(t.get("hk2_practice_hours")),
            note=t.get("note"), created_by=user.id, updated_by=user.id,
        ))

    # ---- Đề tài / nhiệm vụ KHCN ----
    for p in payload.get("projects") or []:
        if not p.get("title"):
            continue
        proj = ResearchProject(
            title=str(p["title"]).strip(), level=p.get("level") or None,
            lead_user_id=user.id, department_id=dept_id, academic_year=academic_year,
            budget_amount=hc.parse_decimal(p.get("budget_amount"), field="budget_amount"),
            status=p.get("task_status") or "ongoing", report_id=rep.id,
            created_by=user.id, updated_by=user.id,
        )
        db.add(proj)
        db.flush()
        db.add(ProjectMember(project_id=proj.id, user_id=user.id,
                             role_in_project=p.get("role") or "lead"))

    # ---- Công bố / Bài báo (domestic|international|conference) ----
    for pub in payload.get("publications") or []:
        if not pub.get("title"):
            continue
        kind = pub.get("pub_kind") or "domestic"
        is_conf = kind == "conference"
        p = Publication(
            title=str(pub["title"]).strip(), journal=pub.get("journal"),
            year=_parse_int(pub.get("year")), doi=pub.get("doi"),
            type="conference" if is_conf else "paper",
            pub_scope=None if is_conf else kind, academic_year=academic_year,
            is_scie=bool(pub.get("is_scie")), is_ssci=bool(pub.get("is_ssci")),
            is_scopus=bool(pub.get("is_scopus")), is_aci=bool(pub.get("is_aci")),
            department_id=dept_id, report_id=rep.id, created_by=user.id, updated_by=user.id,
        )
        db.add(p)
        db.flush()
        db.add(PublicationAuthor(publication_id=p.id, author_order=1, user_id=user.id,
                                 is_corresponding=True, author_role="corresponding"))

    # ---- Hợp đồng KHCN ----
    for c in payload.get("contracts") or []:
        if not c.get("title"):
            continue
        db.add(ResearchContract(
            title=str(c["title"]).strip(), contract_type=c.get("contract_type"),
            value_amount=hc.parse_decimal(c.get("value_amount"), field="value_amount"),
            partner_org=c.get("partner_org"), academic_year=academic_year,
            department_id=dept_id, report_id=rep.id, created_by=user.id, updated_by=user.id,
        ))

    # ---- Công tác khác ----
    for a in payload.get("activities") or []:
        if not a.get("content"):
            continue
        db.add(StaffActivity(
            kind=a.get("kind") or "khac", content=str(a["content"]).strip(),
            academic_year=academic_year, performer_user_id=user.id,
            department_id=dept_id, report_id=rep.id, created_by=user.id, updated_by=user.id,
        ))

    audit_service.log_action(
        db, action="ACTIVITY_REPORT_SUBMIT", resource="activity_report",
        user_id=user.id, resource_id=rep.id, correlation_id=correlation_id, ip=ip,
        detail={"period": period},
    )
    db.commit()
    db.refresh(rep)
    return get_report(db, user=user, report_id=rep.id)


# ===================== READ =====================
def _counts(db: Session, report_id: uuid.UUID) -> dict:
    def n(model):
        return db.execute(
            select(func.count()).select_from(model).where(model.report_id == report_id)
        ).scalar_one()
    return {
        "teaching": n(TeachingCourse), "projects": n(ResearchProject),
        "publications": n(Publication), "contracts": n(ResearchContract),
        "activities": n(StaffActivity),
    }


def _report_dict(db: Session, r: ActivityReport, *, with_counts: bool = True) -> dict:
    d = {
        "id": r.id,
        "reporter_user_id": r.reporter_user_id,
        "reporter_name": hc.user_name(db, r.reporter_user_id),
        "department_id": r.department_id,
        "department_name": hc.dept_name(db, r.department_id),
        "period_label": r.period_label,
        "period_year": r.period_year,
        "academic_year": r.academic_year,
        "status": r.status,
        "note": r.note,
        "submitted_at": r.submitted_at,
        "reviewed_by_name": hc.user_name(db, r.reviewed_by),
        "reviewed_at": r.reviewed_at,
        "created_at": r.created_at,
    }
    if with_counts:
        d["counts"] = _counts(db, r.id)
    return d


def list_reports(db: Session, *, user: CurrentUser, period: Optional[str],
                 department_id: Optional[uuid.UUID], status: Optional[str],
                 page: int, limit: int) -> tuple[list[dict], int]:
    conds = []
    # Người nộp thường chỉ thấy báo cáo của mình; reviewer (office/leader/admin) thấy tất cả.
    if not _can_review(user):
        conds.append(ActivityReport.reporter_user_id == user.id)
    if period:
        conds.append(ActivityReport.period_label == period)
    if department_id:
        conds.append(ActivityReport.department_id == department_id)
    if status:
        conds.append(ActivityReport.status == status)
    total = db.execute(select(func.count()).select_from(ActivityReport).where(*conds)).scalar_one()
    rows = db.execute(
        select(ActivityReport).where(*conds)
        .order_by(ActivityReport.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_report_dict(db, r) for r in rows], total


def get_report(db: Session, *, user: CurrentUser, report_id: uuid.UUID) -> dict:
    r = db.get(ActivityReport, report_id)
    if r is None:
        raise not_found("Không tìm thấy báo cáo")
    if not _can_review(user) and r.reporter_user_id != user.id:
        raise hc.forbidden("Bạn chỉ xem báo cáo của mình")
    d = _report_dict(db, r)
    # kèm các dòng hoạt động
    d["teaching"] = [
        {"id": t.id, "course_name": t.course_name,
         "hk1_theory_hours": t.hk1_theory_hours, "hk1_practice_hours": t.hk1_practice_hours,
         "hk2_theory_hours": t.hk2_theory_hours, "hk2_practice_hours": t.hk2_practice_hours}
        for t in db.execute(select(TeachingCourse).where(TeachingCourse.report_id == report_id)).scalars()
    ]
    d["projects"] = [
        {"id": p.id, "title": p.title, "level": p.level, "status": p.status,
         "budget_amount": str(p.budget_amount) if p.budget_amount is not None else None}
        for p in db.execute(select(ResearchProject).where(ResearchProject.report_id == report_id)).scalars()
    ]
    d["publications"] = [
        {"id": p.id, "title": p.title, "type": p.type, "pub_scope": p.pub_scope, "journal": p.journal,
         "year": p.year, "is_scie": p.is_scie, "is_scopus": p.is_scopus}
        for p in db.execute(select(Publication).where(Publication.report_id == report_id)).scalars()
    ]
    d["contracts"] = [
        {"id": c.id, "title": c.title, "contract_type": c.contract_type,
         "value_amount": str(c.value_amount) if c.value_amount is not None else None}
        for c in db.execute(select(ResearchContract).where(ResearchContract.report_id == report_id)).scalars()
    ]
    d["activities"] = [
        {"id": a.id, "kind": a.kind, "content": a.content}
        for a in db.execute(select(StaffActivity).where(StaffActivity.report_id == report_id)).scalars()
    ]
    return d


# ===================== REVIEW / DELETE =====================
def review_report(db: Session, *, user: CurrentUser, report_id: uuid.UUID, correlation_id, ip) -> dict:
    if not _can_review(user):
        raise hc.forbidden("Chỉ Văn phòng/Lãnh đạo/Quản trị được duyệt báo cáo")
    r = db.get(ActivityReport, report_id)
    if r is None:
        raise not_found("Không tìm thấy báo cáo")
    r.status = "reviewed"
    r.reviewed_by = user.id
    r.reviewed_at = func.now()
    audit_service.log_action(
        db, action="ACTIVITY_REPORT_REVIEW", resource="activity_report",
        user_id=user.id, resource_id=r.id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
    db.refresh(r)
    return _report_dict(db, r)


def delete_report(db: Session, *, user: CurrentUser, report_id: uuid.UUID, correlation_id, ip) -> None:
    r = db.get(ActivityReport, report_id)
    if r is None:
        raise not_found("Không tìm thấy báo cáo")
    # Người nộp xóa báo cáo của mình khi chưa duyệt; reviewer xóa được mọi báo cáo.
    if not _can_review(user):
        if r.reporter_user_id != user.id:
            raise hc.forbidden("Bạn chỉ xóa báo cáo của mình")
        if r.status == "reviewed":
            raise AppException(ErrorCode.REPORT_LOCKED, "Báo cáo đã duyệt — không thể xóa", 422)
    # Xóa các dòng hoạt động thuộc báo cáo (gỡ khỏi module tương ứng).
    # project_members xóa theo CASCADE khi xóa research_projects.
    from sqlalchemy import delete as _del
    for model in (TeachingCourse, ResearchProject, Publication, ResearchContract, StaffActivity):
        db.execute(_del(model).where(model.report_id == report_id))
    db.delete(r)
    audit_service.log_action(
        db, action="ACTIVITY_REPORT_DELETE", resource="activity_report",
        user_id=user.id, resource_id=report_id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
