"""Horas do ciclo de pagamento (BUSINESS-RULES.md §11).

O sistema só calcula as horas; o administrador multiplica pelo valor da hora.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from app.calculation.payroll import PayPeriod, period_containing, period_ending_in
from app.core.clock import today_local
from app.core.errors import AppError
from app.models import Employee
from app.services import employee_service
from app.services.hour_bank_service import Totals, period_totals


@dataclass(frozen=True)
class Payroll:
    employee: Employee
    period: PayPeriod
    totals: Totals
    closed: bool  # o ciclo já terminou (dia do pagamento já passou ou é hoje)


def _period(
    employee: Employee, payment_month: str | None, reference_date: date | None
) -> PayPeriod:
    if payment_month is not None:
        match = re.fullmatch(r"(\d{4})-(\d{2})", payment_month)
        if match is None or not 1 <= int(match.group(2)) <= 12:
            raise AppError(422, "VALIDATION_ERROR", "Mês de pagamento inválido (use AAAA-MM).")
        return period_ending_in(int(match.group(1)), int(match.group(2)), employee.payday)
    return period_containing(reference_date or today_local(), employee.payday)


def _payroll(db: Session, employee: Employee, period: PayPeriod) -> Payroll:
    return Payroll(
        employee=employee,
        period=period,
        totals=period_totals(db, employee, period.start, period.end),
        closed=period.end <= today_local(),
    )


def employee_payroll(
    db: Session, employee_id: int, payment_month: str | None, reference_date: date | None
) -> Payroll:
    employee = employee_service.get(db, employee_id)
    return _payroll(db, employee, _period(employee, payment_month, reference_date))


def summary(
    db: Session,
    *,
    payment_month: str | None,
    reference_date: date | None,
    q: str | None,
    status: Literal["ACTIVE", "INACTIVE"] | None,
    page: int,
    page_size: int,
) -> tuple[list[Payroll], int]:
    """Horas de todos os funcionários, cada um no seu próprio ciclo de pagamento."""
    employees, total = employee_service.list_employees(
        db, q=q, status=status, sort="name", page=page, page_size=page_size
    )
    return [_payroll(db, e, _period(e, payment_month, reference_date)) for e in employees], total
