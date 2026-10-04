"""Cadastro de funcionários e do horário fixo (BUSINESS-RULES.md §2 e §3)."""

from datetime import date, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.clock import now_utc, today_local
from app.core.errors import AppError, conflict, not_found
from app.models import (
    AuditLog,
    BiometricTemplate,
    Employee,
    EmployeeSchedule,
    EmployeeScheduleDay,
)
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, ScheduleCreate, ScheduleDaysIn
from app.services import audit

SORT_FIELDS = {
    "name": func.lower(Employee.name),
    "registration_number": Employee.registration_number,
    "hire_date": Employee.hire_date,
}


def _snapshot(employee: Employee) -> dict[str, Any]:
    return {
        "name": employee.name,
        "registration_number": employee.registration_number,
        "cpf": employee.cpf,
        "hire_date": employee.hire_date,
        "termination_date": employee.termination_date,
        "status": employee.status,
        "payday": employee.payday,
    }


def _schedule_snapshot(schedule: EmployeeSchedule) -> dict[str, Any]:
    return {
        "valid_from": schedule.valid_from,
        "valid_to": schedule.valid_to,
        "weekly_day_off": schedule.weekly_day_off,
        "days": [
            {
                "weekday": d.weekday,
                "start_time": d.start_time,
                "end_time": d.end_time,
                "lunch_minutes": d.lunch_minutes,
            }
            for d in schedule.days
        ],
    }


def _build_days(data: ScheduleDaysIn) -> list[EmployeeScheduleDay]:
    return [
        EmployeeScheduleDay(
            weekday=d.weekday,
            start_time=d.start_time,
            end_time=d.end_time,
            lunch_minutes=d.lunch_minutes,
        )
        for d in sorted(data.days, key=lambda d: d.weekday)
    ]


def _check_unique(
    db: Session, *, registration_number: str | None, cpf: str | None, exclude_id: int | None
) -> None:
    def taken(condition: Any) -> bool:
        query = select(Employee.id).where(condition)
        if exclude_id is not None:
            query = query.where(Employee.id != exclude_id)
        return db.scalar(query) is not None

    if registration_number is not None and taken(
        Employee.registration_number == registration_number
    ):
        raise conflict("CONFLICT", "Já existe um funcionário com esta matrícula.")
    if cpf is not None and taken(Employee.cpf == cpf):
        raise conflict("CONFLICT", "Já existe um funcionário com este CPF.")


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("CONFLICT", "Matrícula ou CPF já cadastrado.") from exc


def get(db: Session, employee_id: int, *, for_update: bool = False) -> Employee:
    query = select(Employee).where(Employee.id == employee_id)
    if for_update:
        query = query.with_for_update()
    employee = db.scalar(query)
    if employee is None:
        raise not_found("Funcionário não encontrado.", code="EMPLOYEE_NOT_FOUND")
    return employee


def list_employees(
    db: Session,
    *,
    q: str | None,
    status: Literal["ACTIVE", "INACTIVE"] | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[Employee], int]:
    query = select(Employee)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Employee.name).like(pattern),
                func.lower(Employee.registration_number).like(pattern),
            )
        )
    if status:
        query = query.where(Employee.status == status)

    descending = sort.startswith("-")
    column = SORT_FIELDS.get(sort.lstrip("-"))
    if column is None:
        raise AppError(
            422, "VALIDATION_ERROR", "Ordenação inválida.", {"allowed": sorted(SORT_FIELDS)}
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ordered = query.order_by(column.desc() if descending else column.asc(), Employee.id)
    items = db.scalars(ordered.offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def create(db: Session, data: EmployeeCreate, actor: audit.Actor) -> Employee:
    _check_unique(db, registration_number=data.registration_number, cpf=data.cpf, exclude_id=None)
    employee = Employee(
        name=data.name,
        registration_number=data.registration_number,
        cpf=data.cpf,
        hire_date=data.hire_date,
        payday=data.payday,
        status="ACTIVE",
    )
    schedule = EmployeeSchedule(
        valid_from=data.hire_date,
        created_by_admin_id=actor.admin_id,
        weekly_day_off=data.schedule.weekly_day_off,
        days=_build_days(data.schedule),
    )
    employee.schedules.append(schedule)
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("CONFLICT", "Matrícula ou CPF já cadastrado.") from exc
    audit.record(
        db,
        actor=actor,
        action="employee.create",
        entity_type="employee",
        entity_id=employee.id,
        after={**_snapshot(employee), "schedule": _schedule_snapshot(schedule)},
    )
    _commit_or_conflict(db)
    return employee


def current_schedule(
    db: Session, employee_id: int, on: date | None = None
) -> EmployeeSchedule | None:
    """Horário vigente na data (padrão: hoje). Se ainda não começou, devolve o próximo."""
    on = on or today_local()
    schedules = db.scalars(
        select(EmployeeSchedule)
        .where(EmployeeSchedule.employee_id == employee_id)
        .options(selectinload(EmployeeSchedule.days))
        .order_by(EmployeeSchedule.valid_from)
    ).all()
    for schedule in schedules:
        if schedule.valid_from <= on and (schedule.valid_to is None or schedule.valid_to >= on):
            return schedule
    upcoming = [s for s in schedules if s.valid_from > on]
    return upcoming[0] if upcoming else None


def update(db: Session, employee_id: int, data: EmployeeUpdate, actor: audit.Actor) -> Employee:
    employee = get(db, employee_id, for_update=True)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "registration_number", "hire_date", "payday"):
        if required in changes and changes[required] is None:
            raise AppError(422, "VALIDATION_ERROR", f"O campo {required} não pode ser vazio.")
    _check_unique(
        db,
        registration_number=changes.get("registration_number"),
        cpf=changes.get("cpf"),
        exclude_id=employee.id,
    )

    before = _snapshot(employee)
    new_hire = changes.get("hire_date", employee.hire_date)
    new_termination = changes.get("termination_date", employee.termination_date)
    if new_termination is not None and new_termination < new_hire:
        raise AppError(
            422, "VALIDATION_ERROR", "A data de desligamento não pode ser anterior à admissão."
        )
    if new_hire != employee.hire_date:
        _move_first_schedule(db, employee.id, new_hire)

    for field, value in changes.items():
        setattr(employee, field, value)
    audit.record(
        db,
        actor=actor,
        action="employee.update",
        entity_type="employee",
        entity_id=employee.id,
        before=before,
        after=_snapshot(employee),
    )
    _commit_or_conflict(db)
    return employee


def _move_first_schedule(db: Session, employee_id: int, new_hire: date) -> None:
    """A primeira vigência de horário sempre começa na admissão (BUSINESS-RULES.md §3.1)."""
    first = db.scalar(
        select(EmployeeSchedule)
        .where(EmployeeSchedule.employee_id == employee_id)
        .order_by(EmployeeSchedule.valid_from)
        .limit(1)
    )
    if first is None:
        return
    if first.valid_to is not None and new_hire > first.valid_to:
        raise conflict(
            "SCHEDULE_OVERLAP",
            "A nova data de admissão é posterior ao fim do primeiro horário cadastrado.",
        )
    first.valid_from = new_hire


def set_active(db: Session, employee_id: int, active: bool, actor: audit.Actor) -> Employee:
    employee = get(db, employee_id, for_update=True)
    status = "ACTIVE" if active else "INACTIVE"
    if employee.status == status:
        return employee
    before = _snapshot(employee)
    employee.status = status
    after = _snapshot(employee)
    if not active:
        # Funcionário desativado deixa de ser reconhecido: templates excluídos (BIOMETRICS.md §6).
        result = db.execute(
            sql_update(BiometricTemplate)
            .where(
                BiometricTemplate.employee_id == employee.id,
                BiometricTemplate.deleted_at.is_(None),
            )
            .values(deleted_at=now_utc())
        )
        after["biometric_templates_deleted"] = int(result.rowcount or 0)  # type: ignore[attr-defined]
    audit.record(
        db,
        actor=actor,
        action="employee.activate" if active else "employee.deactivate",
        entity_type="employee",
        entity_id=employee.id,
        before=before,
        after=after,
    )
    db.commit()
    return employee


def history(db: Session, employee_id: int, page: int, page_size: int) -> tuple[list[AuditLog], int]:
    get(db, employee_id)
    condition = (AuditLog.entity_type == "employee") & (AuditLog.entity_id == employee_id)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(condition)) or 0
    items = db.scalars(
        select(AuditLog)
        .where(condition)
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def list_schedules(db: Session, employee_id: int) -> list[EmployeeSchedule]:
    get(db, employee_id)
    return list(
        db.scalars(
            select(EmployeeSchedule)
            .where(EmployeeSchedule.employee_id == employee_id)
            .options(selectinload(EmployeeSchedule.days))
            .order_by(EmployeeSchedule.valid_from)
        ).all()
    )


def add_schedule(
    db: Session, employee_id: int, data: ScheduleCreate, actor: audit.Actor
) -> EmployeeSchedule:
    """Novo horário a partir de `valid_from`; o vigente é encerrado no dia anterior."""
    employee = get(db, employee_id, for_update=True)  # serializa alterações do mesmo funcionário
    if data.valid_from < employee.hire_date:
        raise conflict("SCHEDULE_OVERLAP", "O horário não pode começar antes da admissão.")
    if employee.termination_date is not None and data.valid_from > employee.termination_date:
        raise conflict("SCHEDULE_OVERLAP", "O horário não pode começar depois do desligamento.")

    latest = db.scalar(
        select(EmployeeSchedule)
        .where(EmployeeSchedule.employee_id == employee_id)
        .order_by(EmployeeSchedule.valid_from.desc())
        .limit(1)
    )
    if latest is not None:
        if data.valid_from <= latest.valid_from:
            raise conflict(
                "SCHEDULE_OVERLAP",
                "O novo horário deve começar depois do início do horário atual.",
                {"current_valid_from": latest.valid_from.isoformat()},
            )
        latest.valid_to = data.valid_from - timedelta(days=1)

    schedule = EmployeeSchedule(
        employee_id=employee_id,
        valid_from=data.valid_from,
        created_by_admin_id=actor.admin_id,
        weekly_day_off=data.weekly_day_off,
        days=_build_days(data),
    )
    db.add(schedule)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="employee.schedule_create",
        entity_type="employee",
        entity_id=employee_id,
        after=_schedule_snapshot(schedule),
    )
    db.commit()
    return schedule
