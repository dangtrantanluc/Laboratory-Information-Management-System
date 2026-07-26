"""Router kho biểu mẫu VILAS (GĐ3) — /forms.

- Template (biểu mẫu gốc): QLCL quản trị (form:manage); mọi vai trò đọc (form:read).
- Submission (minh chứng): phòng lab nộp (form:submit) → thông báo QLCL.
File gắn qua /attachments (owner_type='form_template' | 'form_submission').
"""
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_permission
from app.core.rate_limit import rate_limit
from app.core.responses import ok, paginated, normalize_pagination
from app.db.database import get_db
from app.schemas.form import (
    CreateFormSubmissionRequest,
    CreateFormTemplateRequest,
    RejectFormSubmissionRequest,
    UpdateFormTemplateRequest,
)
from app.services import form_file_service, form_service

router = APIRouter(prefix="/forms", tags=["forms"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== Templates =====
@router.get("/templates")
def list_templates(
    iso_clause: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = form_service.list_templates(
        db, iso_clause=iso_clause, category=category, q=q,
        active_only=active_only, page=p, limit=lim,
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_template(
    body: CreateFormTemplateRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "manage")),
    db: Session = Depends(get_db),
):
    data = form_service.create_template(
        db, user=user, code=body.code, title=body.title, iso_clause=body.iso_clause,
        category=body.category, year=body.year, note=body.note,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.patch("/templates/{template_id}")
def update_template(
    template_id: uuid.UUID,
    body: UpdateFormTemplateRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "manage")),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = form_service.update_template(
        db, user=user, template_id=template_id, changes=changes,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


# ===== Tệp của biểu mẫu gốc (form:manage) =====
@router.post(
    "/templates/{template_id}/file",
    dependencies=[Depends(rate_limit("form-file-upload", limit=30, window_seconds=60))],
)
def upload_template_file(
    template_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    reason: Optional[str] = Form(default=None),
    expected_attachment_id: Optional[uuid.UUID] = Form(default=None),
    user: CurrentUser = Depends(require_permission("form", "manage")),
    db: Session = Depends(get_db),
):
    """Tải lên / thay tệp biểu mẫu. Bản cũ chuyển thành lịch sử, không mất."""
    content = file.file.read()
    data = form_file_service.replace_file(
        db, user=user, owner_type=form_file_service.OWNER_TEMPLATE, owner_id=template_id,
        file_name=file.filename or "file", content=content, mime=file.content_type,
        reason=reason, expected_attachment_id=expected_attachment_id,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.delete("/templates/{template_id}/file")
def delete_template_file(
    template_id: uuid.UUID,
    request: Request,
    reason: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(require_permission("form", "manage")),
    db: Session = Depends(get_db),
):
    data = form_file_service.delete_file(
        db, user=user, owner_type=form_file_service.OWNER_TEMPLATE, owner_id=template_id,
        reason=reason, correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.get("/templates/{template_id}/files")
def template_file_history(
    template_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    """Lịch sử tải lên: mọi bản đã dùng, ai tải, khi nào, vì sao thay."""
    return ok(
        form_file_service.file_history(
            db, user=user, owner_type=form_file_service.OWNER_TEMPLATE, owner_id=template_id
        )
    )


@router.get("/templates/{template_id}/files/{attachment_id}/download")
def download_template_file(
    template_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    """URL tải cho một bản bất kỳ trong lịch sử (kể cả bản đã bị thay)."""
    return ok(
        form_file_service.history_download_url(
            db, user=user, owner_type=form_file_service.OWNER_TEMPLATE,
            owner_id=template_id, attachment_id=attachment_id,
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== Submissions (minh chứng) =====
@router.get("/history")
def forms_history(
    q: Optional[str] = Query(default=None),
    owner_type: Optional[str] = Query(default=None, description="form_template | form_submission"),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=200),
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    """Lịch sử TỔNG HỢP toàn kho biểu mẫu (tải lên / thay thế / gỡ tệp), mới nhất trước."""
    p, lim = normalize_pagination(page, limit)
    items, total = form_file_service.history_feed(
        db, user=user, q=q, owner_type=owner_type, page=p, limit=lim,
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.get("/submissions")
def list_submissions(
    template_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    year: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = form_service.list_submissions(
        db, user=user, template_id=template_id, department_id=department_id,
        year=year, status=status, page=p, limit=lim,
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.get(
    "/submissions/export",
    dependencies=[Depends(rate_limit("report-export", limit=10, window_seconds=60))],
)
def export_submissions(
    request: Request,
    template_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    year: Optional[int] = Query(default=None),
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    content = form_service.export_submissions_xlsx(
        db, user=user, template_id=template_id, department_id=department_id, year=year,
        correlation_id=_cid(request), ip=_ip(request),
    )
    filename = f"vilas-minh-chung{f'-{year}' if year else ''}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/submissions", status_code=status.HTTP_201_CREATED)
def create_submission(
    body: CreateFormSubmissionRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "submit")),
    db: Session = Depends(get_db),
):
    data = form_service.create_submission(
        db, user=user, template_id=body.template_id, department_id=body.department_id,
        year=body.year, note=body.note, correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.post("/submissions/{submission_id}/approve")
def approve_submission(
    submission_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "approve")),
    db: Session = Depends(get_db),
):
    data = form_service.approve_submission(
        db, user=user, submission_id=submission_id,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.post("/submissions/{submission_id}/reject")
def reject_submission(
    submission_id: uuid.UUID,
    body: RejectFormSubmissionRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "approve")),
    db: Session = Depends(get_db),
):
    data = form_service.reject_submission(
        db, user=user, submission_id=submission_id, reject_reason=body.reason,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


# ===== Tệp của minh chứng (form:submit + ràng buộc phòng/trạng thái) =====
@router.post(
    "/submissions/{submission_id}/file",
    dependencies=[Depends(rate_limit("form-file-upload", limit=30, window_seconds=60))],
)
def upload_submission_file(
    submission_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    reason: Optional[str] = Form(default=None),
    expected_attachment_id: Optional[uuid.UUID] = Form(default=None),
    user: CurrentUser = Depends(require_permission("form", "submit")),
    db: Session = Depends(get_db),
):
    """Tải lên / thay tệp minh chứng. Đã duyệt thì khóa; bị từ chối thì quay lại chờ duyệt."""
    content = file.file.read()
    data = form_file_service.replace_file(
        db, user=user, owner_type=form_file_service.OWNER_SUBMISSION,
        owner_id=submission_id, file_name=file.filename or "file", content=content,
        mime=file.content_type, reason=reason,
        expected_attachment_id=expected_attachment_id,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.get("/submissions/{submission_id}/files")
def submission_file_history(
    submission_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    return ok(
        form_file_service.file_history(
            db, user=user, owner_type=form_file_service.OWNER_SUBMISSION,
            owner_id=submission_id,
        )
    )


@router.get("/submissions/{submission_id}/files/{attachment_id}/download")
def download_submission_file(
    submission_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("form", "read")),
    db: Session = Depends(get_db),
):
    return ok(
        form_file_service.history_download_url(
            db, user=user, owner_type=form_file_service.OWNER_SUBMISSION,
            owner_id=submission_id, attachment_id=attachment_id,
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


@router.get("/submissions/{submission_id}/history")
def submission_history(
    submission_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("form", "approve")),
    db: Session = Depends(get_db),
):
    return ok(form_service.submission_history(db, submission_id=submission_id))
