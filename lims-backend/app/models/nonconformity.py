"""Models M8 — Không phù hợp & Hành động khắc phục (NC & CAPA, §7.10/§8.7/§8.4).

4 bảng theo Contract M8 (23-contract-m8-nc-capa.md §1):
- nonconformities: phiếu NC §7.10. Nguồn polymorphic (source_type/source_id) cho phép
  khiếu nại/QC/đánh giá/môi trường/mẫu/PT đổ về cùng engine CAPA. nc_code bất biến
  app-layer; không lộ ID tuần tự. Vòng đời open→in_capa→closed (+cancelled).
- capa: hành động khắc phục §8.7 — 1 CAPA / 1 NC (UNIQUE nc_id). ĐÃ ĐÓNG = BẤT BIẾN:
  trigger DB chặn UPDATE khi OLD.status='closed' + chặn DELETE. Tách người mở/đóng (QM).
- capa_actions: các hành động con của CAPA; đóng CAPA cần mọi action 'done'.
- capa_notification_dedup: chống trùng CRON-7 mốc 7/3/0 — đồng bộ M2/M4/M5 dedup.

CHECK DB là lưới an toàn (enum); nghiệp vụ (chuyển trạng thái, RBAC, QM, dedup) enforce
app-layer. Audit mọi thao tác qua audit_logs (§8.4).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_NC_SOURCE = ("manual", "complaint", "qc", "audit", "env", "sample", "pt")
VALID_NC_SEVERITY = ("minor", "major", "critical")
VALID_NC_STATUS = ("open", "in_capa", "closed", "cancelled")
VALID_CAPA_TYPE = ("corrective", "preventive")
VALID_CAPA_STATUS = ("in_progress", "closed")
VALID_CAPA_EFFECTIVENESS = ("effective", "not_effective")
VALID_ACTION_STATUS = ("todo", "done")
VALID_CAPA_DEDUP_KINDS = ("CAPA_DUE",)


class Nonconformity(Base):
    """Phiếu không phù hợp §7.10 (FR-NC-001..004). Nguồn polymorphic → 1 engine CAPA.

    nc_code bất biến (app); vòng đời open→in_capa→closed. Sau closed app-layer chặn sửa.
    """

    __tablename__ = "nonconformities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nc_code: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'manual'")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    affected_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    raised_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    raised_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'open'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("nc_code", name="uq_nc_code"),
        CheckConstraint(
            "source_type IN ('manual','complaint','qc','audit','env','sample','pt')",
            name="ck_nc_source_type",
        ),
        CheckConstraint(
            "severity IN ('minor','major','critical')", name="ck_nc_severity"
        ),
        CheckConstraint(
            "status IN ('open','in_capa','closed','cancelled')", name="ck_nc_status"
        ),
    )


class Capa(Base):
    """Hành động khắc phục §8.7 (FR-NC-005..008). 1 CAPA / 1 NC (UNIQUE nc_id).

    ĐÃ ĐÓNG = BẤT BIẾN (trigger DB chặn UPDATE khi status='closed' + chặn DELETE).
    Hiệu lực (effectiveness) ghi khi đóng; tách người mở NC ≠ người đóng CAPA (QM).
    """

    __tablename__ = "capa"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nonconformities.id", ondelete="CASCADE"),
        nullable=False,
    )
    capa_type: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'corrective'")
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'in_progress'")
    )
    effectiveness_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    effectiveness_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("nc_id", name="uq_capa_nc"),
        CheckConstraint(
            "capa_type IN ('corrective','preventive')", name="ck_capa_type"
        ),
        CheckConstraint(
            "status IN ('in_progress','closed')", name="ck_capa_status"
        ),
        CheckConstraint(
            "effectiveness_result IS NULL OR effectiveness_result IN ('effective','not_effective')",
            name="ck_capa_effectiveness",
        ),
    )


class CapaAction(Base):
    """Hành động con của CAPA (FR-NC-006). Đóng CAPA cần mọi action 'done'."""

    __tablename__ = "capa_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    capa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capa.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=text("'todo'")
    )
    done_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("status IN ('todo','done')", name="ck_action_status"),
    )


class CapaNotificationDedup(Base):
    """Chống trùng CRON-7 (đồng bộ equipment/chemical/hr_notification_dedup).

    1 dòng / (capa, mốc, ngày). Cron INSERT dòng dedup trước → UNIQUE violation = đã gửi.
    """

    __tablename__ = "capa_notification_dedup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    capa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capa.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    milestone_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fire_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "capa_id", "milestone_days", "fire_date", name="uq_capadedup_capa_ms_date"
        ),
        CheckConstraint("kind IN ('CAPA_DUE')", name="ck_capadedup_kind"),
        CheckConstraint("milestone_days IN (7, 3, 0)", name="ck_capadedup_milestone"),
    )
