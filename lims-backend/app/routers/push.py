"""Router Web Push (M20) — /push. STRICT SELF, không cần RBAC riêng."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.push import PushSubscribeRequest, PushUnsubscribeRequest
from app.services import push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    return ok({"public_key": settings.vapid_public_key})


@router.post("/subscribe")
def subscribe(
    body: PushSubscribeRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    push_service.subscribe(
        db,
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        user_agent=body.user_agent,
    )
    db.commit()
    return ok({})


@router.post("/unsubscribe")
def unsubscribe(
    body: PushUnsubscribeRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    push_service.unsubscribe(db, user_id=user.id, endpoint=body.endpoint)
    db.commit()
    return ok({})
