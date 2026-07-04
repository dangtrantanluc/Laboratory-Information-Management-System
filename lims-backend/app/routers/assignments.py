"""Router assignments (M1) — hủy phân công + kết quả của phân công (FR-005/008/011)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.sample import CreateResultRequest
from app.services import assignment_service, result_service, sample_common

router = APIRouter(prefix="/assignments", tags=["m1-assignments"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_assignment(
    assignment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    assignment_service.cancel_assignment(
        db,
        user=user,
        assignment_id=assignment_id,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{assignment_id}/results")
def get_assignment_result(
    assignment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = result_service.get_assignment_result(
        db, user=user, assignment_id=assignment_id
    )
    if data is None:
        return ok(None)
    if data.get("_not_published"):
        return {"success": True, "data": None, "meta": {"reason": "NOT_PUBLISHED"}}
    return ok(data)


@router.post("/{assignment_id}/results", status_code=status.HTTP_201_CREATED)
def enter_result(
    assignment_id: uuid.UUID,
    body: CreateResultRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = result_service.enter_result(
        db,
        user=user,
        assignment_id=assignment_id,
        result_data=body.result_data,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
