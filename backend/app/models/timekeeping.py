from datetime import date, datetime

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

RECORD_TYPES = ("ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT")


class Device(TimestampMixin, Base):
    """Terminal de ponto (kiosk). O token é exibido uma vez; só o hash é guardado."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TimeRecord(Base):
    """Batida de ponto. Imutável: só pode ser anulada por ajuste (BUSINESS-RULES.md §4.6)."""

    __tablename__ = "time_records"
    __table_args__ = (
        CheckConstraint("type IN ('ENTRY', 'LUNCH_EXIT', 'LUNCH_RETURN', 'EXIT')", name="type"),
        CheckConstraint("source IN ('KIOSK', 'ADJUSTMENT')", name="source"),
        # Duplicidade: um tipo por dia de jornada entre os registros válidos.
        Index(
            "uq_time_records_active_type",
            "employee_id",
            "workday_date",
            "type",
            unique=True,
            postgresql_where=text("voided_at IS NULL"),
        ),
        Index("ix_time_records_employee_recorded", "employee_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    workday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    face_match_score: Mapped[float | None] = mapped_column(REAL)
    device_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("devices.id"))
    ip: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by_adjustment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("time_record_adjustments.id", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    adjustments: Mapped[list["TimeRecordAdjustment"]] = relationship(
        foreign_keys="TimeRecordAdjustment.record_id",
        back_populates="record",
        order_by="TimeRecordAdjustment.id",
    )


class TimeRecordAdjustment(Base):
    __tablename__ = "time_record_adjustments"
    __table_args__ = (
        CheckConstraint("kind IN ('ADD', 'VOID')", name="kind"),
        CheckConstraint("char_length(reason) >= 10", name="reason"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employees.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("time_records.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_admin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    record: Mapped[TimeRecord] = relationship(
        foreign_keys=[record_id], back_populates="adjustments"
    )


class Holiday(TimestampMixin, Base):
    __tablename__ = "holidays"
    __table_args__ = (
        Index("uq_holidays_date", "date", unique=True, postgresql_where=text("NOT recurring")),
        Index(
            "uq_holidays_recurring_month_day",
            text("EXTRACT(MONTH FROM date)"),
            text("EXTRACT(DAY FROM date)"),
            unique=True,
            postgresql_where=text("recurring"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class HourBankEntry(Base):
    """Lançamento manual no banco de horas. Imutável: correção é outro lançamento."""

    __tablename__ = "hour_bank_entries"
    __table_args__ = (
        CheckConstraint("minutes <> 0", name="minutes"),
        CheckConstraint(
            "kind IN ('OPENING_BALANCE', 'COMPENSATION', 'PAYOUT', 'CORRECTION')", name="kind"
        ),
        CheckConstraint("char_length(reason) >= 10", name="reason"),
        Index("ix_hour_bank_entries_employee_date", "employee_id", "entry_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_admin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
