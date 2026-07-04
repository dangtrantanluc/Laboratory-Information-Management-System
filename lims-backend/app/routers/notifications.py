"""Router notifications (M7.5) — STRICT SELF (user_id == current user)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import not_found
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread: Optional[bool] = Query(default=None),
    type_filter: Optional[str] = Query(default=None, alias="type", max_length=50),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = notification_service.list_notifications(
        db,
        user_id=user.id,
        unread=unread,
        type_filter=type_filter,
        page=page,
        limit=limit,
    )
    serialized = [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "ref_type": n.ref_type,
            "ref_id": n.ref_id,
            "read_at": n.read_at,
            "created_at": n.created_at,
        }
        for n in items
    ]
    return paginated(serialized, page=page, limit=limit, total=total)


@router.get("/unread-count")
def get_unread_count(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    return ok({"unread_count": notification_service.unread_count(db, user_id=user.id)})


@router.patch("/read-all")
def mark_all_read(
    type_filter: Optional[str] = Query(default=None, alias="type"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = notification_service.mark_all_read(
        db, user_id=user.id, type_filter=type_filter
    )
    db.commit()
    return ok({"marked_read": count})


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = notification_service.mark_read(
        db, user_id=user.id, notification_id=notification_id
    )
    if notif is None:
        # IDOR-safe: thuộc user khác → 404 (không lộ tồn tại)
        raise not_found("Không tìm thấy thông báo")
    db.commit()
    return ok({"id": notif.id, "read_at": notif.read_at})
