"""Router Thẻ vào PTN (sinh viên) — M19 — /lab-access-cards.

Danh sách quản trị (CRUD, không qua duyệt): Văn phòng (office) quản trị
(lab_access_card:manage); admin/leader/qms/office đọc (lab_access_card:read).
Nhập / xuất Excel theo file gốc của Văn phòng: xem lab_access_excel_service.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.concurrency import upload_slot
from app.core.rate_limit import rate_limit
from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, require_permission
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.lab_access import (
    CreateLabAccessCardRequest,
    LabAccessImportResponse,
    UpdateLabAccessCardRequest,
)
from app.services import lab_access_excel_service, lab_access_service

router = APIRouter(prefix="/lab-access-cards", tags=["lab-access-cards"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


@router.get("")
def list_cards(
    q: Optional[str] = Query(default=None, max_length=100),
    supervisor_name: Optional[str] = Query(default=None, max_length=255),
    room: Optional[str] = Query(default=None, max_length=255),
    active_on: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_permission("lab_access_card", "read")),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = lab_access_service.list_cards(
        db, q=q, supervisor_name=supervisor_name, room=room, active_on=active_on,
        page=page, limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.get(
    "/export.xlsx",
    # Trả file nhị phân — khai tường minh để test hợp đồng API bỏ qua response_model.
    response_class=Response,
    dependencies=[Depends(rate_limit("lab-access-export", limit=20, window_seconds=60))],
)
def export_cards(
    request: Request,
    q: Optional[str] = Query(default=None, max_length=100),
    supervisor_name: Optional[str] = Query(default=None, max_length=255),
    quarter: Optional[int] = Query(default=None, ge=1, le=4, description="Quý ghi trên tiêu đề"),
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    user: CurrentUser = Depends(require_permission("lab_access_card", "read")),
    db: Session = Depends(get_db),
):
    """Xuất Excel đúng bố cục file "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN".

    Quý/năm chỉ để ghi tiêu đề và tên sheet; dữ liệu theo đúng bộ lọc đang xem.
    """
    content, filename = lab_access_excel_service.export_xlsx(
        db, user=user, q=q, supervisor_name=supervisor_name, quarter=quarter, year=year,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=LabAccessImportResponse)
def import_cards(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true = chỉ xem trước, không ghi"),
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    """Nhập danh sách từ file Excel gốc — đối chiếu theo MSSV (có thì sửa, chưa có thì tạo)."""
    with upload_slot():
        content = file.file.read(lab_access_excel_service.IMPORT_MAX_BYTES + 1)
        data = lab_access_excel_service.import_cards(
            db, user=user, content=content, dry_run=dry_run,
            correlation_id=_cid(request), ip=client_ip(request),
        )
    return ok(data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_card(
    body: CreateLabAccessCardRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    data = lab_access_service.create_card(
        db, user=user, payload=body.model_dump(),
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.patch("/{card_id}")
def update_card(
    card_id: uuid.UUID,
    body: UpdateLabAccessCardRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = lab_access_service.update_card(
        db, user=user, card_id=card_id, changes=changes,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    lab_access_service.delete_card(
        db, user=user, card_id=card_id, correlation_id=_cid(request), ip=client_ip(request)
    )
