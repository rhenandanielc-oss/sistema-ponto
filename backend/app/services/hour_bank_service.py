"""Cálculo por período e banco de horas (BUSINESS-RULES.md §5 e §9)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation.records import Punch
from app.calculation.workday import ABSENT, INCOMPLETE, DayInput, DayResult, calculate_day
from app.core.clock import now_utc
from app.core.errors import AppError
from app.models import Employee, HourBankEntry, TimeRecord
from app.schemas.timekeeping import HourBankEntryIn
from app.services import audit, employee_service, holiday_service, settings_service
from app.services.record_service import load_schedules

MAX_PERIOD_DAYS = 366


@dataclass(frozen=True)
class Totals:
    planned_minutes: int = 0
    worked_minutes: int = 0
    late_minutes: int = 0
    early_leave_minutes: int = 0
    missing_minutes: int = 0
    overtime_minutes: int = 0
    night_minutes: int = 0
    balance_minutes: int = 0
    absences: int = 0
    incomplete_days: int = 0


@dataclass(frozen=True)
class HourBank:
    days: list[DayResult]
    totals: Totals
    opening_balance_minutes: int
    entries: list[HourBankEntry]
    entries_minutes: int
    closing_balance_minutes: int


def validate_period(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise AppError(
            422, "VALIDATION_ERROR", "A data inicial deve ser anterior ou igual à final."
        )
    if (date_to - date_from).days + 1 > MAX_PERIOD_DAYS:
        raise AppError(422, "VALIDATION_ERROR", f"O período máximo é de {MAX_PERIOD_DAYS} dias.")


def _calculate(db: Session, employee: Employee, date_from: date, date_to: date) -> list[DayResult]:
    """Resultado diário de `date_from` a `date_to`, inclusive. Sem limite de período (interno)."""
    rules = settings_service.rules(settings_service.load(db))
    table = load_schedules(db, employee.id)
    holidays = holiday_service.holiday_dates(db, date_from, date_to)
    punches: dict[date, list[Punch]] = defaultdict(list)
    for record in db.scalars(
        select(TimeRecord).where(
            TimeRecord.employee_id == employee.id,
            TimeRecord.voided_at.is_(None),
            TimeRecord.workday_date >= date_from,
            TimeRecord.workday_date <= date_to,
        )
    ):
        punches[record.workday_date].append(Punch(record.type, record.recorded_at))

    now = now_utc()
    results = []
    day = date_from
    while day <= date_to:
        employed = employee.hire_date <= day and (
            employee.termination_date is None or day <= employee.termination_date
        )
        inp = DayInput(
            day=day,
            schedule=table.day_schedule(day),
            employed=employed,
            holiday=day in holidays,
            punches=tuple(punches.get(day, ())),
        )
        results.append(calculate_day(inp, rules, now))
        day += timedelta(days=1)
    return results


def _totals(days: list[DayResult]) -> Totals:
    return Totals(
        planned_minutes=sum(d.planned_minutes for d in days),
        worked_minutes=sum(d.worked_minutes for d in days),
        late_minutes=sum(d.late_minutes for d in days),
        early_leave_minutes=sum(d.early_leave_minutes for d in days),
        missing_minutes=sum(d.missing_minutes for d in days if d.counts_for_bank),
        overtime_minutes=sum(d.overtime_minutes for d in days if d.counts_for_bank),
        night_minutes=sum(d.night_minutes for d in days),
        balance_minutes=sum(d.balance_minutes for d in days if d.counts_for_bank),
        absences=sum(1 for d in days if d.status == ABSENT),
        incomplete_days=sum(1 for d in days if d.status == INCOMPLETE),
    )


def workdays(
    db: Session, employee_id: int, date_from: date, date_to: date
) -> tuple[list[DayResult], Totals]:
    validate_period(date_from, date_to)
    employee = employee_service.get(db, employee_id)
    days = _calculate(db, employee, date_from, date_to)
    return days, _totals(days)


def hour_bank(db: Session, employee_id: int, date_from: date, date_to: date) -> HourBank:
    validate_period(date_from, date_to)
    employee = employee_service.get(db, employee_id)
    days = _calculate(db, employee, date_from, date_to)

    # Saldo anterior: todos os dias desde a admissão até a véspera do período + lançamentos.
    opening_days = (
        _calculate(db, employee, employee.hire_date, date_from - timedelta(days=1))
        if employee.hire_date < date_from
        else []
    )
    all_entries = db.scalars(
        select(HourBankEntry)
        .where(HourBankEntry.employee_id == employee_id, HourBankEntry.entry_date <= date_to)
        .order_by(HourBankEntry.entry_date, HourBankEntry.id)
    ).all()
    before = [e for e in all_entries if e.entry_date < date_from]
    within = [e for e in all_entries if e.entry_date >= date_from]

    opening = sum(d.balance_minutes for d in opening_days if d.counts_for_bank) + sum(
        e.minutes for e in before
    )
    totals = _totals(days)
    entries_minutes = sum(e.minutes for e in within)
    return HourBank(
        days=days,
        totals=totals,
        opening_balance_minutes=opening,
        entries=list(within),
        entries_minutes=entries_minutes,
        closing_balance_minutes=opening + totals.balance_minutes + entries_minutes,
    )


def list_entries(db: Session, employee_id: int) -> list[HourBankEntry]:
    employee_service.get(db, employee_id)
    return list(
        db.scalars(
            select(HourBankEntry)
            .where(HourBankEntry.employee_id == employee_id)
            .order_by(HourBankEntry.entry_date, HourBankEntry.id)
        ).all()
    )


def add_entry(
    db: Session, employee_id: int, data: HourBankEntryIn, actor: audit.Actor
) -> HourBankEntry:
    employee_service.get(db, employee_id)
    if actor.admin_id is None:
        raise AppError(403, "FORBIDDEN", "Somente administradores fazem lançamentos.")
    entry = HourBankEntry(
        employee_id=employee_id,
        entry_date=data.entry_date,
        minutes=data.minutes,
        kind=data.kind,
        reason=data.reason,
        created_by_admin_id=actor.admin_id,
    )
    db.add(entry)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="hour_bank.entry_create",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "entry_id": entry.id,
            "entry_date": data.entry_date,
            "minutes": data.minutes,
            "kind": data.kind,
            "reason": data.reason,
        },
    )
    db.commit()
    return entry
