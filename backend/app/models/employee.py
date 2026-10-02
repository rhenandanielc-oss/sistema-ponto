from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

EMPLOYEE_STATUSES = ("ACTIVE", "INACTIVE")


class Employee(TimestampMixin, Base):
    """Funcionário. Não tem login: é identificado pelo rosto no kiosk (SECURITY.md §1)."""

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status"),
        CheckConstraint(
            "termination_date IS NULL OR termination_date >= hire_date", name="termination_date"
        ),
        CheckConstraint("cpf IS NULL OR cpf ~ '^[0-9]{11}$'", name="cpf_digits"),
        CheckConstraint("payday BETWEEN 1 AND 31", name="payday"),
        Index("ix_employees_name_lower", text("lower(name)")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    registration_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cpf: Mapped[str | None] = mapped_column(Text, unique=True)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="ACTIVE", index=True)
    # Dia do mês em que o funcionário recebe; define o ciclo de pagamento (BUSINESS-RULES.md §11).
    payday: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    schedules: Mapped[list["EmployeeSchedule"]] = relationship(
        back_populates="employee", order_by="EmployeeSchedule.valid_from"
    )


class EmployeeSchedule(Base):
    """Vigência do horário fixo do funcionário (BUSINESS-RULES.md §3)."""

    __tablename__ = "employee_schedules"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        # A restrição EXCLUDE (sem sobreposição de vigências) é criada na migration.
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employees.id"), nullable=False, index=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped[Employee] = relationship(back_populates="schedules")
    days: Mapped[list["EmployeeScheduleDay"]] = relationship(
        back_populates="schedule",
        order_by="EmployeeScheduleDay.weekday",
        cascade="all, delete-orphan",
    )


class EmployeeScheduleDay(Base):
    __tablename__ = "employee_schedule_days"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday"),
        CheckConstraint("lunch_minutes >= 0", name="lunch_minutes"),
    )

    schedule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employee_schedules.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Almoço livre: guarda só a duração prevista, descontada da carga (BUSINESS-RULES.md §3).
    lunch_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="60")

    schedule: Mapped[EmployeeSchedule] = relationship(back_populates="days")
