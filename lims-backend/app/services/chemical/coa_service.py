"""Đính kèm MSDS/CoA của lô.

Tách từ chemical_service.py (850 dòng) — M-03/T1.2.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.chemical import (
    Chemical,
)
from app.services import audit_service, chemical_common as cc

logger_action_prefix = "CHEMICAL"




_COA_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_COA_MAX_BYTES = 20 * 1024 * 1024  # 20MB


def upload_coa(
    db: Session,
    *,
    user,
    lot_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime,
    correlation_id=None,
    ip=None,
) -> dict:
    """Upload chứng chỉ phân tích (CoA) cho lô — gắn theo lô (mỗi lô 1 CoA, ghi đè nếu có).

    RBAC: chỉ vai trò được ghi hóa chất + trong phạm vi phòng của hóa chất (BR-CHEM-018).
    """
    from app.services import storage_service

    lot = cc.get_lot_or_404(db, lot_id)
    chem = db.get(Chemical, lot.chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)

    if mime is None or mime.lower() not in _COA_ALLOWED_MIME:
        raise cc.err("INVALID_FILE_TYPE", "Chỉ chấp nhận PDF/PNG/JPG/XLSX", 422)
    if len(content) > _COA_MAX_BYTES:
        raise cc.err("FILE_TOO_LARGE", "File vượt quá 20MB", 422)

    file_key = storage_service.build_object_key("chem_lot_coa", lot_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)
    lot.coa_file_key = file_key
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_LOT_COA_UPLOAD",
        resource="chemical_lot",
        user_id=user.id,
        resource_id=lot_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"file_name": file_name, "size": len(content)},
    )
    db.commit()
    return {"lot_id": lot_id, "has_coa": True, "file_name": file_name}


def get_coa(db: Session, *, lot_id: uuid.UUID) -> dict:
    lot = cc.get_lot_or_404(db, lot_id)
    if not lot.coa_file_key:
        raise not_found("Lô chưa có file CoA")
    from app.config import settings
    from app.services import storage_service

    file_name = lot.coa_file_key.split("_", 1)[-1]
    url = storage_service.presigned_get_url(lot.coa_file_key, file_name=file_name)
    return {
        "file_name": file_name,
        "mime": "application/pdf",
        "download_url": url,
        "url_expires_at": (
            datetime.now(timezone.utc).timestamp() + settings.presigned_url_ttl_seconds
        ),
    }
