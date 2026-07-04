"""Models M5 — Quản lý Thiết bị & Hiệu chuẩn (Equipment & Calibration, §6.4/§6.5/§8.4).

3 bảng theo Contract M5 Schema (17-contract-m5-schema.md §2):
- equipments: thiết bị §6.4. next_due_date denormalize = next_due của lần hiệu chuẩn
  gần nhất (D3, BR-EQP-008). Chu kỳ value+unit cả 2 NULL = không diện hiệu chuẩn (D4).
  code bất biến app-layer (BR-EQP-014); soft-delete qua deleted_at (D9).
- calibration_records: lần hiệu chuẩn §6.4/§6.5 — IMMUTABLE (D5): trigger DB chặn
  UPDATE/DELETE + KHÔNG route PATCH/DELETE. Đính chính = bản ghi mới (correction_of).
- equipment_notification_dedup: chống trùng CRON-5 mốc 30/15/7 (D8) — đồng bộ M2/M4.

CHECK DB là lưới an toàn (enum, cặp value/unit); nghiệp vụ (tính next_due, denormalize,
badge runtime, RBAC scope) enforce app-layer.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_EQUIPMENT_STATUS = ("active", "maintenance", "broken", "retired")
VALID_CYCLE_UNITS = ("month", "year")
VALID_CALIBRATION_RESULTS = ("pass", "fail")
VALID_EQ_DEDUP_KINDS = ("CALIBRATION_DUE",)


class Equipment(Base):
    """Thiết bị §6.4 (FR-EQP-001..005). Vùng chứa 0..n calibration_records.

    code bất biến (BR-EQP-014, app); next_due_date denormalize = next_due của lần hiệu
    chuẩn gần nhất (BR-EQP-008). Chu kỳ NULL = không diện hiệu chuẩn (BR-EQP-010).
    """

    __tablename__ = "equipments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'active'")
    )
    calibration_cycle_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibration_cycle_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_equip_code"),
        CheckConstraint(
            "status IN ('active', 'maintenance', 'broken', 'retired')",
            name="ck_equip_status",
        ),
        CheckConstraint(
            "calibration_cycle_value IS NULL OR calibration_cycle_value > 0",
            name="ck_equip_cycle_value",
        ),
        CheckConstraint(
            "calibration_cycle_unit IS NULL OR calibration_cycle_unit IN ('month', 'year')",
            name="ck_equip_cycle_unit",
        ),
        CheckConstraint(
            "(calibration_cycle_value IS NULL AND calibration_cycle_unit IS NULL) "
            "OR (calibration_cycle_value IS NOT NULL AND calibration_cycle_unit IS NOT NULL)",
            name="ck_equip_cycle_pair",
        ),
    )


class CalibrationRecord(Base):
    """Lần hiệu chuẩn §6.4/§6.5 (FR-EQP-006..009). BẤT BIẾN (D5, §8.4): trigger DB chặn
    UPDATE/DELETE + KHÔNG route PATCH/DELETE. Đính chính = bản ghi mới (correction_of).

    next_due tự tính = calibrated_at + chu kỳ (cho override D7); CoC/cert qua attachments
    (owner_type='calibration', owner_id=this.id) — D10; cert_file_key là quick-link.
    """

    __tablename__ = "calibration_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    calibrated_at: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    cert_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_records.id", ondelete="RESTRICT"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_due_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # KHÔNG updated_at/updated_by/deleted_at: bản ghi BẤT BIẾN append-only (D5, §8.4)

    __table_args__ = (
        CheckConstraint("result IN ('pass', 'fail')", name="ck_cal_result"),
    )


class EquipmentNotificationDedup(Base):
    """Chống trùng CRON-5 (D8, BR-EQP-011) — đồng bộ chemical/hr_notification_dedup.

    1 dòng/(thiết bị, mốc, ngày). Gửi cho cả người phụ trách + trưởng nhóm vẫn idempotent
    theo thiết bị×mốc×ngày (cron INSERT dòng dedup trước → UNIQUE violation = đã gửi).
    """

    __tablename__ = "equipment_notification_dedup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    milestone_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fire_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "equipment_id", "milestone_days", "fire_date",
            name="uq_eqdedup_eq_ms_date",
        ),
        CheckConstraint("kind IN ('CALIBRATION_DUE')", name="ck_eqdedup_kind"),
        CheckConstraint(
            "milestone_days IN (30, 15, 7)", name="ck_eqdedup_milestone"
        ),
    )
