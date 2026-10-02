from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import DbSession, PageParams, get_current_admin
from app.schemas.common import Page
from app.services import payroll_service

router = APIRouter(tags=["pagamento"], dependencies=[Depends(get_current_admin)])

PaymentMonth = Annotated[
    str | None,
    Query(
        pattern=r"^\d{4}-\d{2}$",
        description="Mês do pagamento (AAAA-MM). Sem ele, usa o ciclo que contém reference_date.",
    ),
]
ReferenceDate = Annotated[
    date | None, Query(description="Data dentro do ciclo desejado (padrão: hoje)")
]


def _hours(minutes: int) -> float:
    return round(minutes / 60, 2)


class PayrollOut(BaseModel):
    employee_id: int
    name: str
    registration_number: str
    payday: int
    period_start: date
    period_end: date
    payment_date: date
    closed: bool = Field(description="false = ciclo em andamento; as horas ainda podem mudar")
    worked_minutes: int
    worked_hours: float = Field(description="Horas trabalhadas em decimal (7h30 = 7.5)")
    planned_minutes: int = Field(description="Horas fixas (salário): carga prevista no ciclo")
    planned_hours: float
    overtime_minutes: int
    overtime_hours: float
    missing_minutes: int
    missing_hours: float
    balance_minutes: int
    payable_minutes: int = Field(description="Horas fixas + extras − faltantes")
    payable_hours: float = Field(
        description="Horas a pagar em decimal (multiplicar pelo valor da hora)"
    )
    absences: int
    incomplete_days: int = Field(description="Dias com batida faltando: corrija antes de pagar")


def _out(p: payroll_service.Payroll) -> PayrollOut:
    t = p.totals
    # Horas a pagar = horas fixas (salário) + extras − faltantes (BUSINESS-RULES.md §11).
    payable = t.planned_minutes + t.overtime_minutes - t.missing_minutes
    return PayrollOut(
        employee_id=p.employee.id,
        name=p.employee.name,
        registration_number=p.employee.registration_number,
        payday=p.employee.payday,
        period_start=p.period.start,
        period_end=p.period.end,
        payment_date=p.period.payment_date,
        closed=p.closed,
        worked_minutes=t.worked_minutes,
        worked_hours=_hours(t.worked_minutes),
        planned_minutes=t.planned_minutes,
        planned_hours=_hours(t.planned_minutes),
        overtime_minutes=t.overtime_minutes,
        overtime_hours=_hours(t.overtime_minutes),
        missing_minutes=t.missing_minutes,
        missing_hours=_hours(t.missing_minutes),
        balance_minutes=t.balance_minutes,
        payable_minutes=payable,
        payable_hours=_hours(payable),
        absences=t.absences,
        incomplete_days=t.incomplete_days,
    )


@router.get("/employees/{employee_id}/payroll", response_model=PayrollOut)
def employee_payroll(
    employee_id: int,
    db: DbSession,
    payment_month: PaymentMonth = None,
    reference_date: ReferenceDate = None,
) -> PayrollOut:
    """Horas do funcionário no ciclo de pagamento. O valor é calculado pelo administrador."""
    return _out(payroll_service.employee_payroll(db, employee_id, payment_month, reference_date))


@router.get("/payroll", response_model=Page[PayrollOut])
def payroll_summary(
    db: DbSession,
    pagination: PageParams,
    payment_month: PaymentMonth = None,
    reference_date: ReferenceDate = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Literal["ACTIVE", "INACTIVE"] | None = "ACTIVE",
) -> Page[PayrollOut]:
    """Horas de todos os funcionários, cada um no seu ciclo de pagamento."""
    items, total = payroll_service.summary(
        db,
        payment_month=payment_month,
        reference_date=reference_date,
        q=q,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(
        items=[_out(p) for p in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
