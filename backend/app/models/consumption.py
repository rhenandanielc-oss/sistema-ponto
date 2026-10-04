"""Consumo do funcionário (BUSINESS-RULES.md §12): itens com preço e lançamentos por funcionário.

Valores em centavos (inteiros) para não ter erro de arredondamento.
"""

from datetime import date, datetime

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ConsumptionItem(TimestampMixin, Base):
    """Item que o funcionário pode consumir (ex.: "Refrigerante lata", R$ 6,00)."""

    __tablename__ = "consumption_items"
    __table_args__ = (
        CheckConstraint("price_cents > 0", name="price"),
        Index("uq_consumption_items_name", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class ConsumptionEntry(Base):
    """Consumo lançado para um funcionário. O preço é copiado do item no momento do lançamento.

    Não é apagado: um lançamento errado é cancelado (com motivo) e continua no histórico.
    """

    __tablename__ = "consumption_entries"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        CheckConstraint("unit_price_cents > 0", name="unit_price"),
        CheckConstraint(
            "(canceled_at IS NULL) = (cancel_reason IS NULL)", name="cancel_consistency"
        ),
        Index("ix_consumption_entries_employee_date", "employee_id", "entry_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("consumption_items.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_admin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("admins.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.id"))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents
