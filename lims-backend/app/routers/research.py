"""Router M4.3 — Thành tích NCKH: đề tài, bài báo/sáng chế, hướng dẫn SV, đăng ký lab
(có duyệt), giảng dạy, cộng đồng, thống kê + Excel.

Kế toán bị CẤM toàn bộ nhóm NCKH (hc.assert_research_access → 403). Scope staff own
enforce ở service. Tác giả/thành viên ngoài hệ thống qua external_name (XOR).
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import AppException
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.hr import (
    CreateCommunityRequest,
    CreateMentorshipRequest,
    CreateProjectRequest,
    CreatePublicationRequest,
    CreateRegistrationRequest,
    CreateTeachingRequest,
    DecideRegistrationRequest,
    ReplaceAuthorsRequest,
    ReplaceMembersRequest,
    UpdateCommunityRequest,
    UpdateMentorshipRequest,
    UpdateProjectRequest,
    UpdatePublicationRequest,
    UpdateTeachingRequest,
)
from app.services import (
    attachment_service,
    hr_common as hc,
    research_report_service,
    research_service,
)

router = APIRouter(tags=["m4-research"])

_PUB_MIME_WHITELIST = {"application/pdf", "image/png", "image/jpeg"}


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _guard(user: CurrentUser) -> CurrentUser:
    """Chặn accountant khỏi toàn bộ nhóm NCKH (BR-HR-023)."""
    hc.assert_research_access(user)
    return user


def _members_payload(items) -> list:
    return [m.model_dump() for m in items]


# ===================== ĐỀ TÀI =====================
@router.get("/research-projects")
def list_projects(
    q: Optional[str] = Query(default=None, max_length=100),
    department_id: Optional[uuid.UUID] = Query(default=None),
    level: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    lead_user_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_projects(
        db,
        user=user,
        q=q,
        department_id=department_id,
        level=level,
        year=year,
        lead_user_id=lead_user_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/research-projects", status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    payload = body.model_dump()
    payload["members"] = _members_payload(body.members)
    return ok(
        research_service.create_project(
            db, user=user, payload=payload, correlation_id=_cid(request), ip=_ip(request)
        )
    )


@router.get("/research-projects/{project_id}")
def get_project(
    project_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(research_service.get_project(db, user=user, project_id=project_id))


@router.patch("/research-projects/{project_id}")
def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.update_project(
            db,
            user=user,
            project_id=project_id,
            changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.delete("/research-projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    research_service.delete_project(
        db, user=user, project_id=project_id, correlation_id=_cid(request), ip=_ip(request)
    )


@router.put("/research-projects/{project_id}/members")
def replace_members(
    project_id: uuid.UUID,
    body: ReplaceMembersRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.replace_project_members(
            db,
            user=user,
            project_id=project_id,
            members=_members_payload(body.members),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===================== PUBLICATIONS =====================
def _pub_payload(body) -> dict:
    payload = body.model_dump()
    # index_code là alias của category (contract dùng cả hai tên)
    if payload.get("category") is None and payload.get("index_code") is not None:
        payload["category"] = payload["index_code"]
    payload.pop("index_code", None)
    return payload


@router.get("/publications")
def list_publications(
    q: Optional[str] = Query(default=None, max_length=100),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    year: Optional[int] = Query(default=None),
    index_code: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    author_user_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_publications(
        db,
        user=user,
        q=q,
        type_filter=type_filter,
        year=year,
        category=category or index_code,
        department_id=department_id,
        author_user_id=author_user_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/publications", status_code=status.HTTP_201_CREATED)
def create_publication(
    body: CreatePublicationRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    payload = _pub_payload(body)
    payload["authors"] = [a.model_dump() for a in body.authors]
    return ok(
        research_service.create_publication(
            db, user=user, payload=payload, correlation_id=_cid(request), ip=_ip(request)
        )
    )


@router.get("/publications/{pub_id}")
def get_publication(
    pub_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(research_service.get_publication(db, user=user, pub_id=pub_id))


@router.patch("/publications/{pub_id}")
def update_publication(
    pub_id: uuid.UUID,
    body: UpdatePublicationRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    changes = body.model_dump(exclude_unset=True)
    if "category" not in changes and "index_code" in changes:
        changes["category"] = changes["index_code"]
    changes.pop("index_code", None)
    return ok(
        research_service.update_publication(
            db,
            user=user,
            pub_id=pub_id,
            changes=changes,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.delete("/publications/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication(
    pub_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    research_service.delete_publication(
        db, user=user, pub_id=pub_id, correlation_id=_cid(request), ip=_ip(request)
    )


@router.put("/publications/{pub_id}/authors")
def replace_authors(
    pub_id: uuid.UUID,
    body: ReplaceAuthorsRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.replace_authors(
            db,
            user=user,
            pub_id=pub_id,
            authors=[a.model_dump() for a in body.authors],
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.post("/publications/{pub_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_publication_attachment(
    pub_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    # scope check qua get_publication (raises FORBIDDEN/404 nếu ngoài scope)
    research_service.get_publication(db, user=user, pub_id=pub_id)
    if file.content_type not in _PUB_MIME_WHITELIST:
        raise AppException(
            "INVALID_FILE_TYPE", "Định dạng file không hợp lệ (PDF/PNG/JPG)", 422
        )
    content = await file.read()
    data = attachment_service.create_attachment(
        db,
        user=user,
        owner_type="publication",
        owner_id=pub_id,
        file_name=file.filename or "publication",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== HƯỚNG DẪN SV =====================
@router.get("/student-mentorships")
def list_mentorships(
    mentor_id: Optional[uuid.UUID] = Query(default=None),
    year: Optional[int] = Query(default=None),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_mentorships(
        db,
        user=user,
        mentor_id=mentor_id,
        year=year,
        type_filter=type_filter,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/student-mentorships", status_code=status.HTTP_201_CREATED)
def create_mentorship(
    body: CreateMentorshipRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.create_mentorship(
            db,
            user=user,
            payload=body.model_dump(),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.patch("/student-mentorships/{mid}")
def update_mentorship(
    mid: uuid.UUID,
    body: UpdateMentorshipRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.update_mentorship(
            db,
            user=user,
            mid=mid,
            changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.delete("/student-mentorships/{mid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mentorship(
    mid: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    research_service.delete_mentorship(
        db, user=user, mid=mid, correlation_id=_cid(request), ip=_ip(request)
    )


# ===================== ĐĂNG KÝ LAB =====================
@router.get("/lab-registrations")
def list_registrations(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    mentor_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_registrations(
        db,
        user=user,
        status_filter=status_filter,
        mentor_id=mentor_id,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/lab-registrations", status_code=status.HTTP_201_CREATED)
def create_registration(
    body: CreateRegistrationRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.create_registration(
            db,
            user=user,
            payload=body.model_dump(),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.post("/lab-registrations/{reg_id}/approve")
def approve_registration(
    reg_id: uuid.UUID,
    request: Request,
    body: DecideRegistrationRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    reason = body.reason if body else None
    return ok(
        research_service.decide_registration(
            db,
            user=user,
            reg_id=reg_id,
            decision="approved",
            reason=reason,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.post("/lab-registrations/{reg_id}/reject")
def reject_registration(
    reg_id: uuid.UUID,
    request: Request,
    body: DecideRegistrationRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    reason = body.reason if body else None
    return ok(
        research_service.decide_registration(
            db,
            user=user,
            reg_id=reg_id,
            decision="rejected",
            reason=reason,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===================== GIẢNG DẠY =====================
@router.get("/teaching-courses")
def list_teaching(
    user_id: Optional[uuid.UUID] = Query(default=None),
    year: Optional[int] = Query(default=None),
    semester: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_teaching(
        db,
        user=user,
        user_id=user_id,
        year=year,
        semester=semester,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/teaching-courses", status_code=status.HTTP_201_CREATED)
def create_teaching(
    body: CreateTeachingRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.create_teaching(
            db,
            user=user,
            payload=body.model_dump(),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.patch("/teaching-courses/{tid}")
def update_teaching(
    tid: uuid.UUID,
    body: UpdateTeachingRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.update_teaching(
            db,
            user=user,
            tid=tid,
            changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.delete("/teaching-courses/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teaching(
    tid: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    research_service.delete_teaching(
        db, user=user, tid=tid, correlation_id=_cid(request), ip=_ip(request)
    )


# ===================== CỘNG ĐỒNG =====================
@router.get("/community-services")
def list_community(
    performer_user_id: Optional[uuid.UUID] = Query(default=None),
    year: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    page, limit = normalize_pagination(page, limit)
    items, total = research_service.list_community(
        db,
        user=user,
        performer_user_id=performer_user_id,
        year=year,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/community-services", status_code=status.HTTP_201_CREATED)
def create_community(
    body: CreateCommunityRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.create_community(
            db,
            user=user,
            payload=body.model_dump(),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.patch("/community-services/{cid}")
def update_community(
    cid: uuid.UUID,
    body: UpdateCommunityRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.update_community(
            db,
            user=user,
            cid=cid,
            changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.delete("/community-services/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community(
    cid: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    research_service.delete_community(
        db, user=user, cid=cid, correlation_id=_cid(request), ip=_ip(request)
    )


# ===================== THỐNG KÊ (#37 / #37b) =====================
@router.get("/research-achievements/stats")
def achievement_stats(
    group_by: str = Query(...),
    user_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    level: Optional[str] = Query(default=None),
    index_code: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    return ok(
        research_service.achievement_stats(
            db,
            user=user,
            group_by=group_by,
            user_id=user_id,
            department_id=department_id,
            date_from=date_from,
            date_to=date_to,
            level=level,
            category=index_code,
        )
    )


@router.get("/research-achievements/stats.xlsx")
def achievement_stats_xlsx(
    request: Request,
    group_by: str = Query(...),
    user_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    level: Optional[str] = Query(default=None),
    index_code: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(user)
    content = research_report_service.export_stats_xlsx(
        db,
        user=user,
        group_by=group_by,
        user_id=user_id,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
        level=level,
        category=index_code,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="research-achievements.xlsx"'},
    )
