"""Router M3 — Quản lý Tài liệu (Document Control, 20 endpoint theo 15-contract-m3-api.md).

LƯU Ý thứ tự đăng ký: các path tĩnh (/documents/pending-review, /documents/access-stats,
/documents/access-stats/export) PHẢI khai báo TRƯỚC /documents/{document_id} (tránh
nuốt path). Kế toán cấm mọi endpoint ghi; phạm vi phòng + 2 mức bảo mật enforce service.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.document import (
    ApproveVersionRequest,
    RejectVersionRequest,
    UpdateDocumentRequest,
    UpdateVersionRequest,
)
from app.services import document_service, document_version_service as dvs

router = APIRouter(prefix="/documents", tags=["m3-documents"])

# router danh mục riêng (path khác /documents)
lookup_router = APIRouter(tags=["m3-documents"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== 1. Danh mục loại tài liệu =====
@lookup_router.get("/document-types")
def list_document_types(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.list_document_types(db))


# ===== 2. Danh mục mức bảo mật =====
@lookup_router.get("/confidentiality-levels")
def list_confidentiality_levels(
    user: CurrentUser = Depends(get_current_user),
):
    return ok(document_service.list_confidentiality_levels())


# ===== 17. Pending review (TRƯỚC /{document_id}) =====
@router.get("/pending-review")
def pending_review(
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = dvs.list_pending_review(
        db, user=user, department_id=department_id, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== 19. Access stats aggregate (TRƯỚC /{document_id}) =====
@router.get("/access-stats")
def access_stats_aggregate(
    from_: Optional[date] = Query(default=None, alias="from"),
    to_: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    action: Optional[str] = Query(default=None),
    top: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="download"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        document_service.aggregate_access_stats(
            db,
            user=user,
            from_=from_,
            to_=to_,
            department_id=department_id,
            action=action,
            top=top,
            sort_by=sort_by,
        )
    )


# ===== 20. Access stats export (TRƯỚC /{document_id}) =====
@router.get("/access-stats/export")
def access_stats_export(
    request: Request,
    from_: Optional[date] = Query(default=None, alias="from"),
    to_: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    action: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = document_service.export_access_stats_xlsx(
        db,
        user=user,
        from_=from_,
        to_=to_,
        department_id=department_id,
        action=action,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="document-access-stats.xlsx"'
        },
    )


# ===== 3. List / search documents =====
@router.get("")
def list_documents(
    q: Optional[str] = Query(default=None, max_length=100),
    type: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    security_level: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = document_service.list_documents(
        db,
        user=user,
        q=q,
        type_filter=type,
        department_id=department_id,
        security_level=security_level,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== 4. Create document + first version (multipart) =====
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    request: Request,
    title: str = Form(...),
    type: str = Form(...),
    department_id: Optional[uuid.UUID] = Form(default=None),
    security_level: Optional[str] = Form(default=None),
    change_note: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    data = document_service.create_document(
        db,
        user=user,
        title=title,
        type_code=type,
        department_id=department_id,
        security_level=security_level,
        change_note=change_note,
        file_name=file.filename or "document",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== 5. Document detail =====
@router.get("/{document_id}")
def get_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        document_service.get_document_detail(db, user=user, document_id=document_id)
    )


# ===== 6. Update document metadata =====
@router.patch("/{document_id}")
def update_document(
    document_id: uuid.UUID,
    body: UpdateDocumentRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = document_service.update_document(
        db,
        user=user,
        document_id=document_id,
        title=body.title,
        type_code=body.type,
        security_level=body.security_level,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== 7. Soft-delete document =====
@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        document_service.delete_document(
            db,
            user=user,
            document_id=document_id,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===== 16. History =====
@router.get("/{document_id}/history")
def document_history(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(document_service.get_history(db, user=user, document_id=document_id))


# ===== 18. Access stats single document =====
@router.get("/{document_id}/access-stats")
def document_access_stats(
    document_id: uuid.UUID,
    from_: Optional[date] = Query(default=None, alias="from"),
    to_: Optional[date] = Query(default=None, alias="to"),
    group_by: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        document_service.document_access_stats(
            db,
            user=user,
            document_id=document_id,
            from_=from_,
            to_=to_,
            group_by=group_by,
        )
    )


# ===== 8. List versions =====
@router.get("/{document_id}/versions")
def list_versions(
    document_id: uuid.UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = dvs.list_versions(
        db,
        user=user,
        document_id=document_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== 9. Create new version (multipart) =====
@router.post("/{document_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_version(
    document_id: uuid.UUID,
    request: Request,
    change_note: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    data = dvs.create_version(
        db,
        user=user,
        document_id=document_id,
        change_note=change_note,
        file_name=file.filename or "document",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== 10. Get single version =====
@router.get("/{document_id}/versions/{version_id}")
def get_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        dvs.get_version(db, user=user, document_id=document_id, version_id=version_id)
    )


# ===== 11. Update version (draft) — change_note JSON =====
@router.patch("/{document_id}/versions/{version_id}")
def update_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    body: UpdateVersionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = dvs.update_version(
        db,
        user=user,
        document_id=document_id,
        version_id=version_id,
        change_note=body.change_note,
        file_name=None,
        content=None,
        mime=None,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== 11b. Update version file (multipart, thay file draft) =====
@router.put("/{document_id}/versions/{version_id}/file")
async def replace_version_file(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    change_note: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    data = dvs.update_version(
        db,
        user=user,
        document_id=document_id,
        version_id=version_id,
        change_note=change_note,
        file_name=file.filename or "document",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== 12. Submit review =====
@router.post("/{document_id}/versions/{version_id}/submit-review")
def submit_review(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        dvs.submit_review(
            db,
            user=user,
            document_id=document_id,
            version_id=version_id,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===== 13. Approve =====
@router.post("/{document_id}/versions/{version_id}/approve")
def approve_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    body: Optional[ApproveVersionRequest] = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        dvs.approve_version(
            db,
            user=user,
            document_id=document_id,
            version_id=version_id,
            note=body.note if body else None,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===== 14. Reject =====
@router.post("/{document_id}/versions/{version_id}/reject")
def reject_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    body: RejectVersionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        dvs.reject_version(
            db,
            user=user,
            document_id=document_id,
            version_id=version_id,
            reject_reason=body.reject_reason,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===== 15. Download version =====
@router.get("/{document_id}/versions/{version_id}/download")
def download_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        dvs.download_version(
            db,
            user=user,
            document_id=document_id,
            version_id=version_id,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )
