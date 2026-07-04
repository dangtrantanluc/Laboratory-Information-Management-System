"""Router M4 — danh mục đọc (#38-#41). Đã seed; CRUD danh mục thuộc admin/seed."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import hr_catalog_service

router = APIRouter(prefix="/catalogs", tags=["m4-catalogs"])


@router.get("/project-levels")
def project_levels(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(hr_catalog_service.project_levels(db))


@router.get("/pub-indexes")
def pub_indexes(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(hr_catalog_service.pub_indexes(db))


@router.get("/contract-types")
def contract_types(
    user: CurrentUser = Depends(require_roles("admin", "leader", "accountant")),
    db: Session = Depends(get_db),
):
    return ok(hr_catalog_service.contract_types(db))


@router.get("/mentorship-types")
def mentorship_types(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(hr_catalog_service.mentorship_types(db))
