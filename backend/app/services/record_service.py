"""Batidas de ponto e ajustes (BUSINESS-RULES.md §4)."""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any, Literal, NoReturn

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.calculation.records import (
    ENTRY,
    EXIT,
    Punch,
    allowed_next,
    is_valid_order,
    workday_for_new_entry,
)
from app.calculation.schedule import DaySchedule
from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError, conflict, not_found
from app.core.request_context import current_request
from app.models import Employee, EmployeeSchedule, TimeRecord, TimeRecordAdjustment
from app.schemas.timekeeping import AddRecordAdjustment, VoidRecordAdjustment
from app.services import audit, settings_service

TYPE_LABELS = {
    "ENTRY": "Entrada",
    "LUNCH_EXIT": "Saída para almoço",
    "LUNCH_RETURN": "Retorno do almoço",
    "EXIT": "Saída",
}


# --- Horário vigente ----------------------------------------------------------------------------


class ScheduleTable:
    """Vigências de horário de um funcionário, consultáveis por data."""

    def __init__(self, schedules: list[EmployeeSchedule]) -> None:
        self._schedules = schedules

    def vigente(self, day: date) -> EmployeeSchedule | None:
        for s in self._schedules:
            if s.valid_from <= day and (s.valid_to is None or day <= s.valid_to):
                return s
        return None

    def day_schedule(self, day: date) -> DaySchedule | None:
        schedule = self.vigente(day)
        if schedule is None:
            return None
        for d in schedule.days:
            if d.weekday == day.weekday():
                return DaySchedule(d.weekday, d.start_time, d.end_time, d.lunch_minutes)
        return None

    def as_lookup(self) -> Callable[[date], DaySchedule | None]:
        return self.day_schedule


def load_schedules(db: Session, employee_id: int) -> ScheduleTable:
    schedules = db.scalars(
        select(EmployeeSchedule)
        .where(EmployeeSchedule.employee_id == employee_id)
        .options(selectinload(EmployeeSchedule.days))
        .order_by(EmployeeSchedule.valid_from)
    ).all()
    return ScheduleTable(list(schedules))


def _punches(records: list[TimeRecord]) -> list[Punch]:
    return [Punch(r.type, r.recorded_at) for r in records]


def _active_records(db: Session, employee_id: int, workday: date) -> list[TimeRecord]:
    return list(
        db.scalars(
            select(TimeRecord)
            .where(
                TimeRecord.employee_id == employee_id,
                TimeRecord.workday_date == workday,
                TimeRecord.voided_at.is_(None),
            )
            .order_by(TimeRecord.recorded_at)
        ).all()
    )


def _last_record(db: Session, employee_id: int) -> TimeRecord | None:
    return db.scalar(
        select(TimeRecord)
        .where(TimeRecord.employee_id == employee_id, TimeRecord.voided_at.is_(None))
        .order_by(TimeRecord.recorded_at.desc(), TimeRecord.id.desc())
        .limit(1)
    )


def _is_employed(employee: Employee, day: date) -> bool:
    return employee.hire_date <= day and (
        employee.termination_date is None or day <= employee.termination_date
    )


# --- Batida (kiosk) -----------------------------------------------------------------------------


def _reject(
    db: Session,
    error: AppError,
    *,
    employee_id: int | None,
    record_type: str,
    actor: audit.Actor,
) -> NoReturn:
    """Desfaz a transação, audita a tentativa rejeitada e levanta o erro (BUSINESS-RULES §4.5)."""
    db.rollback()
    audit.record(
        db,
        actor=actor,
        action="record.rejected",
        entity_type="employee" if employee_id else None,
        entity_id=employee_id,
        after={"type": record_type, "code": error.code},
    )
    db.commit()
    raise error


def _workday_for(
    db: Session, employee_id: int, at: datetime, table: ScheduleTable
) -> tuple[date, list[TimeRecord]]:
    """Dia de jornada de uma nova batida: o turno aberto ou um novo dia (BUSINESS-RULES §4.4)."""
    company = settings_service.load(db)
    last = _last_record(db, employee_id)
    if last is not None:
        records = _active_records(db, employee_id, last.workday_date)
        types = {r.type for r in records}
        entry = next((r for r in records if r.type == ENTRY), None)
        open_cycle = entry is not None and EXIT not in types
        if (
            open_cycle
            and entry
            and at - entry.recorded_at <= timedelta(hours=company.max_shift_hours)
        ):
            return last.workday_date, records
    workday = workday_for_new_entry(
        at,
        table.as_lookup(),
        get_settings().tz,
        timedelta(hours=company.early_entry_window_hours),
    )
    return workday, _active_records(db, employee_id, workday)


def create_record(
    db: Session,
    *,
    employee_id: int,
    record_type: str,
    actor: audit.Actor,
    device_id: int | None = None,
    face_match_score: float | None = None,
) -> TimeRecord:
    """Registra uma batida com o horário oficial do servidor (usada pelo kiosk)."""
    now = now_utc()
    tz = get_settings().tz

    def reject(error: AppError) -> NoReturn:
        _reject(
            db,
            error,
            employee_id=employee_id if exists else None,
            record_type=record_type,
            actor=actor,
        )

    # Bloqueia o funcionário: batidas simultâneas da mesma pessoa são serializadas.
    employee = db.scalar(select(Employee).where(Employee.id == employee_id).with_for_update())
    exists = employee is not None
    if employee is None:
        reject(not_found("Funcionário não encontrado.", code="EMPLOYEE_NOT_FOUND"))
    if employee.status != "ACTIVE" or not _is_employed(employee, now.astimezone(tz).date()):
        reject(conflict("EMPLOYEE_INACTIVE", "Funcionário inativo."))

    table = load_schedules(db, employee_id)
    workday, day_records = _workday_for(db, employee_id, now, table)
    if table.vigente(workday) is None:
        reject(conflict("NO_APPLICABLE_SCHEDULE", "Funcionário sem horário cadastrado para hoje."))

    company = settings_service.load(db)
    last = _last_record(db, employee_id)
    min_gap = timedelta(minutes=company.min_minutes_between_records)
    if last is not None and now - last.recorded_at < min_gap:
        reject(
            conflict(
                "DUPLICATE_RECORD", "Batida já registrada há instantes.", {"last_type": last.type}
            )
        )
    if record_type in {r.type for r in day_records}:
        reject(
            conflict(
                "DUPLICATE_RECORD",
                f"{TYPE_LABELS[record_type]} já registrada neste dia.",
                {"type": record_type},
            )
        )
    allowed = allowed_next(_punches(day_records))
    if record_type not in allowed:
        expected = ", ".join(TYPE_LABELS[t] for t in allowed) or "nenhuma (dia encerrado)"
        reject(
            conflict(
                "INVALID_SEQUENCE",
                f"Batida fora de sequência. Próxima batida esperada: {expected}.",
                {"expected": list(allowed)},
            )
        )

    req = current_request()
    record = TimeRecord(
        employee_id=employee_id,
        type=record_type,
        recorded_at=now,
        workday_date=workday,
        source="KIOSK",
        device_id=device_id,
        face_match_score=face_match_score,
        ip=req.ip if req else None,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        reject(conflict("DUPLICATE_RECORD", "Batida já registrada.", {"type": record_type}))
    audit.record(
        db,
        actor=actor,
        action="record.create",
        entity_type="time_record",
        entity_id=record.id,
        after=_record_snapshot(record),
    )
    db.commit()
    return record


def allowed_types(db: Session, employee_id: int) -> tuple[date, tuple[str, ...]]:
    """Dia de jornada e tipos de batida possíveis agora (o kiosk habilita só estes botões)."""
    table = load_schedules(db, employee_id)
    now = now_utc()
    workday, records = _workday_for(db, employee_id, now, table)
    return workday, allowed_next(_punches(records))


def _record_snapshot(r: TimeRecord) -> dict[str, Any]:
    return {
        "employee_id": r.employee_id,
        "type": r.type,
        "recorded_at": r.recorded_at,
        "workday_date": r.workday_date,
        "source": r.source,
        "device_id": r.device_id,
    }


# --- Ajustes do administrador -------------------------------------------------------------------


def add_record(db: Session, data: AddRecordAdjustment, actor: audit.Actor) -> TimeRecordAdjustment:
    """Inclui uma batida esquecida (BUSINESS-RULES.md §4.6)."""
    tz = get_settings().tz
    employee = db.scalar(select(Employee).where(Employee.id == data.employee_id).with_for_update())
    if employee is None:
        raise not_found("Funcionário não encontrado.", code="EMPLOYEE_NOT_FOUND")
    recorded_at = data.recorded_at
    workday = data.workday_date or recorded_at.astimezone(tz).date()

    if recorded_at > now_utc():
        raise AppError(422, "VALIDATION_ERROR", "A batida não pode estar no futuro.")
    if recorded_at.astimezone(tz).date() not in (workday, workday + timedelta(days=1)):
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "O horário deve estar no dia de jornada ou no dia seguinte (turno noturno).",
        )
    if not _is_employed(employee, workday):
        raise conflict("EMPLOYEE_INACTIVE", "Data fora do período de contrato do funcionário.")
    if load_schedules(db, employee.id).vigente(workday) is None:
        raise conflict("NO_APPLICABLE_SCHEDULE", "Funcionário sem horário cadastrado nesta data.")

    day_records = _active_records(db, employee.id, workday)
    if data.type in {r.type for r in day_records}:
        raise conflict(
            "DUPLICATE_RECORD",
            f"{TYPE_LABELS[data.type]} já existe neste dia.",
            {"type": data.type},
        )
    if not is_valid_order([*_punches(day_records), Punch(data.type, recorded_at)]):
        raise conflict(
            "INVALID_SEQUENCE", "O horário informado deixa as batidas do dia fora de ordem."
        )

    record = TimeRecord(
        employee_id=employee.id,
        type=data.type,
        recorded_at=recorded_at,
        workday_date=workday,
        source="ADJUSTMENT",
    )
    db.add(record)
    db.flush()
    adjustment = TimeRecordAdjustment(
        employee_id=employee.id,
        kind="ADD",
        record_id=record.id,
        reason=data.reason,
        created_by_admin_id=_admin_id(actor),
    )
    db.add(adjustment)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="record.adjust_add",
        entity_type="time_record",
        entity_id=record.id,
        after={**_record_snapshot(record), "reason": data.reason},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("DUPLICATE_RECORD", "Batida já existe neste dia.") from exc
    return adjustment


def void_record(
    db: Session, data: VoidRecordAdjustment, actor: audit.Actor
) -> TimeRecordAdjustment:
    """Anula uma batida errada. Ela continua no histórico, marcada como anulada."""
    record = db.scalar(select(TimeRecord).where(TimeRecord.id == data.record_id).with_for_update())
    if record is None:
        raise not_found("Batida não encontrada.")
    if record.voided_at is not None:
        raise conflict("CONFLICT", "Esta batida já foi anulada.")
    adjustment = TimeRecordAdjustment(
        employee_id=record.employee_id,
        kind="VOID",
        record_id=record.id,
        reason=data.reason,
        created_by_admin_id=_admin_id(actor),
    )
    db.add(adjustment)
    db.flush()
    record.voided_at = now_utc()
    record.voided_by_adjustment_id = adjustment.id
    audit.record(
        db,
        actor=actor,
        action="record.adjust_void",
        entity_type="time_record",
        entity_id=record.id,
        before=_record_snapshot(record),
        after={"voided": True, "reason": data.reason},
    )
    db.commit()
    return adjustment


def _admin_id(actor: audit.Actor) -> int:
    if actor.admin_id is None:
        raise AppError(403, "FORBIDDEN", "Somente administradores fazem ajustes.")
    return actor.admin_id


# --- Consultas ----------------------------------------------------------------------------------


def get_detail(db: Session, record_id: int) -> tuple[TimeRecord, str]:
    row = db.execute(
        select(TimeRecord, Employee.name)
        .join(Employee, Employee.id == TimeRecord.employee_id)
        .where(TimeRecord.id == record_id)
        .options(selectinload(TimeRecord.adjustments))
    ).first()
    if row is None:
        raise not_found("Batida não encontrada.")
    return row[0], row[1]


def list_records(
    db: Session,
    *,
    employee_id: int | None,
    date_from: date | None,
    date_to: date | None,
    record_type: str | None,
    source: str | None,
    device_id: int | None,
    include_voided: bool,
    sort: Literal["recorded_at", "-recorded_at"],
    page: int,
    page_size: int,
) -> tuple[list[tuple[TimeRecord, str]], int]:
    query = select(TimeRecord, Employee.name).join(Employee, Employee.id == TimeRecord.employee_id)
    if employee_id is not None:
        query = query.where(TimeRecord.employee_id == employee_id)
    if date_from is not None:
        query = query.where(TimeRecord.workday_date >= date_from)
    if date_to is not None:
        query = query.where(TimeRecord.workday_date <= date_to)
    if record_type is not None:
        query = query.where(TimeRecord.type == record_type)
    if source is not None:
        query = query.where(TimeRecord.source == source)
    if device_id is not None:
        query = query.where(TimeRecord.device_id == device_id)
    if not include_voided:
        query = query.where(TimeRecord.voided_at.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = TimeRecord.recorded_at.desc() if sort.startswith("-") else TimeRecord.recorded_at.asc()
    rows = db.execute(
        query.order_by(order, TimeRecord.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [(r[0], r[1]) for r in rows], total


def list_adjustments(
    db: Session, employee_id: int | None, page: int, page_size: int
) -> tuple[list[TimeRecordAdjustment], int]:
    query = select(TimeRecordAdjustment)
    if employee_id is not None:
        query = query.where(TimeRecordAdjustment.employee_id == employee_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(TimeRecordAdjustment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total
