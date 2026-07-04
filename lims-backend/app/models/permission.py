"""Models permissions + roles_permissions — RBAC dữ liệu hóa (D4)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    CheckConstraint,
    UniqueConstraint,
    ForeignKeyConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_SCOPES = ("all", "department", "own")


class Permission(Base):
    """Danh mục resource × action chuẩn hóa (seed cố định)."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_perm_resource_action"),
    )


class RolePermission(Base):
    """Ma trận quyền role × resource × action × scope (R13). Seed từ RBAC matrix."""

    __tablename__ = "roles_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'all'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("role", "resource", "action", name="uq_rp_role_res_act"),
        CheckConstraint(
            "role IN ('admin', 'leader', 'accountant', 'staff')", name="ck_rp_role"
        ),
        CheckConstraint(
            "scope IN ('all', 'department', 'own')", name="ck_rp_scope"
        ),
        ForeignKeyConstraint(
            ["resource", "action"],
            ["permissions.resource", "permissions.action"],
            name="fk_rp_permission",
            ondelete="CASCADE",
        ),
    )
