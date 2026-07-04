"""Models M2 — Quản lý Hóa chất & Tồn kho (Chemical Inventory).

6 bảng theo Contract M2 Schema (03-contract-m2-schema.md):
units, chemicals, chemical_lots, chemical_transactions,
chemical_recheck_records, chemical_notification_dedup.

NUMERIC không float (Decimal xuyên suốt). chemical_transactions IMMUTABLE — không expose
route sửa/xóa (BR-CHEM-015). CHECK DB là lưới an toàn; nghiệp vụ enforce ở app-layer.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_MEASUREMENT_GROUPS = ("mass", "volume", "count")
VALID_TXN_TYPES = ("in", "out", "adjust")
VALID_RECHECK_RESULTS = ("pass", "fail")
VALID_CHEMICAL_STATUS = ("active", "inactive")
VALID_DEDUP_KINDS = ("CHEM_EXPIRY", "CHEM_RECHECK_DUE")


class Unit(Base):
    """Danh mục đơn vị + hệ số quy đổi (seed cố định — BR-CHEM-029). Natural PK = code."""

    __tablename__ = "units"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    measurement_group: Mapped[str] = mapped_column(String(10), nullable=False)
    factor_to_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "measurement_group IN ('mass', 'volume', 'count')", name="ck_units_group"
        ),
        CheckConstraint("factor_to_base > 0", name="ck_units_factor"),
        UniqueConstraint("code", "measurement_group", name="uq_units_code_group"),
    )


class Chemical(Base):
    """Danh mục hóa chất (FR-CHEM-001). status=inactive là soft-delete."""

    __tablename__ = "chemicals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cas_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    measurement_group: Mapped[str] = mapped_column(String(10), nullable=False)
    hazard_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reorder_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'active'")
    )
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

    __table_args__ = (
        ForeignKeyConstraint(
            ["base_unit", "measurement_group"],
            ["units.code", "units.measurement_group"],
            ondelete="RESTRICT",
            name="fk_chem_baseunit",
        ),
        UniqueConstraint(
            "department_id", "name", "cas_no", name="uq_chem_dept_name_cas"
        ),
        CheckConstraint(
            "measurement_group IN ('mass', 'volume', 'count')", name="ck_chem_group"
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_chem_status"),
        CheckConstraint(
            "reorder_threshold IS NULL OR reorder_threshold >= 0",
            name="ck_chem_reorder",
        ),
    )


class ChemicalLot(Base):
    """Lô hóa chất (FR-CHEM-002). qty_base = tồn hiện tại theo base unit (maintain bởi
    giao dịch trong txn có row-lock — D7)."""

    __tablename__ = "chemical_lots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    chemical_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chemicals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lot_no: Mapped[str] = mapped_column(String(64), nullable=False)
    qty_base: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default=text("0")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    price_unit: Mapped[str] = mapped_column(
        String(16), ForeignKey("units.code", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'VND'")
    )
    received_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recheck_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recheck_result: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_expired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    coa_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
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

    __table_args__ = (
        UniqueConstraint("chemical_id", "lot_no", name="uq_lot_chem_lotno"),
        CheckConstraint("qty_base >= 0", name="ck_lot_qty"),
        CheckConstraint("unit_price >= 0", name="ck_lot_price"),
        CheckConstraint(
            "recheck_result IS NULL OR recheck_result IN ('pass', 'fail')",
            name="ck_lot_recheck_result",
        ),
        CheckConstraint(
            "recheck_date IS NULL OR expiry_date IS NULL OR recheck_date <= expiry_date",
            name="ck_lot_date_order",
        ),
    )


class ChemicalTransaction(Base):
    """Giao dịch hóa chất IMMUTABLE (BR-CHEM-015). qty_base luôn base unit;
    balance_after snapshot tồn lô sau giao dịch (không SUM runtime)."""

    __tablename__ = "chemical_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chemical_lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    qty_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    base_unit: Mapped[str] = mapped_column(
        String(16), ForeignKey("units.code", ondelete="RESTRICT"), nullable=False
    )
    qty_input: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    input_unit: Mapped[str] = mapped_column(
        String(16), ForeignKey("units.code", ondelete="RESTRICT"), nullable=False
    )
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    price_unit: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("units.code", ondelete="RESTRICT"), nullable=True
    )
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    ref_sample_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="RESTRICT"),
        nullable=True,
    )
    warning_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    by_user: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("type IN ('in', 'out', 'adjust')", name="ck_txn_type"),
        CheckConstraint("balance_after >= 0", name="ck_txn_balance"),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0", name="ck_txn_price"
        ),
        CheckConstraint(
            "(type IN ('in', 'out') AND qty_base > 0) "
            "OR (type = 'adjust' AND qty_base <> 0)",
            name="ck_txn_qty_sign",
        ),
        CheckConstraint(
            "type <> 'out' OR ref_sample_id IS NOT NULL", name="ck_txn_out_sample"
        ),
        CheckConstraint(
            "type <> 'adjust' OR (note IS NOT NULL AND length(btrim(note)) > 0)",
            name="ck_txn_adjust_note",
        ),
    )


class ChemicalRecheckRecord(Base):
    """Lịch sử kiểm tra lại lô (FR-CHEM-011). Cập nhật lot.recheck_result/recheck_date
    theo bản ghi mới nhất."""

    __tablename__ = "chemical_recheck_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chemical_lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    checked_at: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[str] = mapped_column(String(4), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_recheck_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("result IN ('pass', 'fail')", name="ck_recheck_result"),
    )


class ChemicalNotificationDedup(Base):
    """Chống trùng notification cron CRON-6 (FR-CHEM-012 AC2, BR-CHEM-021)."""

    __tablename__ = "chemical_notification_dedup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chemical_lots.id", ondelete="CASCADE"),
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
            "lot_id", "kind", "milestone_days", "fire_date",
            name="uq_dedup_lot_kind_ms_date",
        ),
        CheckConstraint(
            "kind IN ('CHEM_EXPIRY', 'CHEM_RECHECK_DUE')", name="ck_dedup_kind"
        ),
        CheckConstraint(
            "milestone_days IN (30, 15, 7)", name="ck_dedup_milestone"
        ),
    )
