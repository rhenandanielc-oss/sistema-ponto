from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import Actor, DbSession, PageParams, get_current_admin
from app.calculation.workday import DayResult
from app.schemas.common import Page
from app.schemas.timekeeping import (
    DayOut,
    HourBankEntryIn,
    HourBankEntryOut,
    HourBankOut,
    HourBankSummaryItem,
    PunchOut,
    Totals,
    WorkdaysOut,
)
from app.services import hour_bank_service

router = APIRouter(
    prefix="/employees/{employee_id}",
    tags=["cálculo e banco de horas"],
    dependencies=[Depends(get_current_admin)],
)

DateFrom = Annotated[date, Query(description="Data inicial (inclusiva)")]
DateTo = Annotated[date, Query(description="Data final (inclusiva)")]


def day_out(d: DayResult) -> DayOut:
    return DayOut(
        date=d.day,
        day_type=d.day_type,
        status=d.status,
        flags=list(d.flags),
        expected_start=d.expected_start,
        expected_end=d.expected_end,
        planned_minutes=d.planned_minutes,
        worked_minutes=d.worked_minutes,
        break_minutes=d.break_minutes,
        late_minutes=d.late_minutes,
        early_leave_minutes=d.early_leave_minutes,
        missing_minutes=d.missing_minutes,
        overtime_minutes=d.overtime_minutes,
        night_minutes=d.night_minutes,
        night_minutes_reduced=d.night_minutes_reduced,
        balance_minutes=d.balance_minutes,
        counts_for_bank=d.counts_for_bank,
        punches=[PunchOut(type=p.type, at=p.at) for p in d.punches],
    )


@router.get("/workdays", response_model=WorkdaysOut)
def workdays(employee_id: int, date_from: DateFrom, date_to: DateTo, db: DbSession) -> WorkdaysOut:
    days, totals = hour_bank_service.workdays(db, employee_id, date_from, date_to)
    return WorkdaysOut(
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        days=[day_out(d) for d in days],
        totals=Totals.model_validate(totals, from_attributes=True),
    )


@router.get("/hour-bank", response_model=HourBankOut)
def hour_bank(employee_id: int, date_from: DateFrom, date_to: DateTo, db: DbSession) -> HourBankOut:
    bank = hour_bank_service.hour_bank(db, employee_id, date_from, date_to)
    return HourBankOut(
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        days=[day_out(d) for d in bank.days],
        totals=Totals.model_validate(bank.totals, from_attributes=True),
        opening_balance_minutes=bank.opening_balance_minutes,
        entries=[HourBankEntryOut.model_validate(e) for e in bank.entries],
        entries_minutes=bank.entries_minutes,
        closing_balance_minutes=bank.closing_balance_minutes,
    )


@router.get("/hour-bank/entries", response_model=list[HourBankEntryOut])
def list_entries(employee_id: int, db: DbSession) -> list[HourBankEntryOut]:
    return [
        HourBankEntryOut.model_validate(e) for e in hour_bank_service.list_entries(db, employee_id)
    ]


@router.post("/hour-bank/entries", response_model=HourBankEntryOut, status_code=201)
def add_entry(
    employee_id: int, data: HourBankEntryIn, db: DbSession, actor: Actor
) -> HourBankEntryOut:
    return HourBankEntryOut.model_validate(
        hour_bank_service.add_entry(db, employee_id, data, actor)
    )


summary_router = APIRouter(
    prefix="/hour-bank",
    tags=["cálculo e banco de horas"],
    dependencies=[Depends(get_current_admin)],
)


@summary_router.get("/summary", response_model=Page[HourBankSummaryItem])
def hour_bank_summary(
    date_from: DateFrom,
    date_to: DateTo,
    db: DbSession,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=100, description="Nome ou matrícula")] = None,
    status: Literal["ACTIVE", "INACTIVE"] | None = None,
) -> Page[HourBankSummaryItem]:
    """Saldo do banco de horas de todos os funcionários no período, ordenado por nome."""
    rows, total = hour_bank_service.summary(
        db,
        date_from=date_from,
        date_to=date_to,
        q=q,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    items = [
        HourBankSummaryItem(
            employee_id=e.id,
            name=e.name,
            registration_number=e.registration_number,
            status=e.status,
            opening_balance_minutes=b.opening_balance_minutes,
            planned_minutes=b.totals.planned_minutes,
            worked_minutes=b.totals.worked_minutes,
            overtime_minutes=b.totals.overtime_minutes,
            missing_minutes=b.totals.missing_minutes,
            period_balance_minutes=b.totals.balance_minutes,
            entries_minutes=b.entries_minutes,
            closing_balance_minutes=b.closing_balance_minutes,
            absences=b.totals.absences,
            incomplete_days=b.totals.incomplete_days,
        )
        for e, b in rows
    ]
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)
