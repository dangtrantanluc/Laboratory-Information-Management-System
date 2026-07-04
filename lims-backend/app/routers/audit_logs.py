"""Router audit-logs (M7.4) — CHỈ đọc (append-only). admin + leader."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.services import audit_read_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
audit_roles = require_roles("admin", "leader")


@router.get("")
def list_audit_logs(
    user_id: Optional[uuid.UUID] = Query(default=None),
    action: Optional[str] = Query(default=None, max_length=80),
    resource: Optional[str] = Query(default=None, max_length=50),
    resource_id: Optional[uuid.UUID] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    ip: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(audit_roles),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = audit_read_service.list_audit_logs(
        db,
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        correlation_id=correlation_id,
        date_from=date_from,
        date_to=date_to,
        ip=ip,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.get("/{audit_id}")
def get_audit_log(
    audit_id: uuid.UUID,
    user: CurrentUser = Depends(audit_roles),
    db: Session = Depends(get_db),
):
    return ok(audit_read_service.get_audit_log(db, audit_id))
