from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import Actor, DbSession, PageParams, get_current_admin
from app.schemas.common import Page
from app.schemas.employee import (
    AuditEntryOut,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeOut,
    EmployeeUpdate,
    ScheduleCreate,
    ScheduleOut,
)
from app.services import employee_service

router = APIRouter(
    prefix="/employees", tags=["funcionários"], dependencies=[Depends(get_current_admin)]
)


def _detail(db: DbSession, employee_id: int) -> EmployeeDetail:
    employee = employee_service.get(db, employee_id)
    schedule = employee_service.current_schedule(db, employee_id)
    return EmployeeDetail.model_validate(
        {
            **EmployeeOut.model_validate(employee).model_dump(),
            "current_schedule": ScheduleOut.model_validate(schedule) if schedule else None,
        }
    )


@router.get("", response_model=Page[EmployeeOut])
def list_employees(
    db: DbSession,
    pagination: PageParams,
    q: Annotated[str | None, Query(max_length=100, description="Nome ou matrícula")] = None,
    status: Literal["ACTIVE", "INACTIVE"] | None = None,
    sort: Annotated[
        str, Query(description="name, registration_number ou hire_date; prefixo - inverte")
    ] = "name",
) -> Page[EmployeeOut]:
    items, total = employee_service.list_employees(
        db, q=q, status=status, sort=sort, page=pagination.page, page_size=pagination.page_size
    )
    return Page(
        items=[EmployeeOut.model_validate(e) for e in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("", response_model=EmployeeDetail, status_code=201)
def create_employee(data: EmployeeCreate, db: DbSession, actor: Actor) -> EmployeeDetail:
    employee = employee_service.create(db, data, actor)
    return _detail(db, employee.id)


@router.get("/{employee_id}", response_model=EmployeeDetail)
def get_employee(employee_id: int, db: DbSession) -> EmployeeDetail:
    return _detail(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeDetail)
def update_employee(
    employee_id: int, data: EmployeeUpdate, db: DbSession, actor: Actor
) -> EmployeeDetail:
    employee_service.update(db, employee_id, data, actor)
    return _detail(db, employee_id)


@router.post("/{employee_id}/activate", response_model=EmployeeDetail)
def activate_employee(employee_id: int, db: DbSession, actor: Actor) -> EmployeeDetail:
    employee_service.set_active(db, employee_id, True, actor)
    return _detail(db, employee_id)


@router.post("/{employee_id}/deactivate", response_model=EmployeeDetail)
def deactivate_employee(employee_id: int, db: DbSession, actor: Actor) -> EmployeeDetail:
    employee_service.set_active(db, employee_id, False, actor)
    return _detail(db, employee_id)


@router.get("/{employee_id}/history", response_model=Page[AuditEntryOut])
def employee_history(
    employee_id: int, db: DbSession, pagination: PageParams
) -> Page[AuditEntryOut]:
    items, total = employee_service.history(db, employee_id, pagination.page, pagination.page_size)
    return Page(
        items=[AuditEntryOut.model_validate(i) for i in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/{employee_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(employee_id: int, db: DbSession) -> list[ScheduleOut]:
    return [ScheduleOut.model_validate(s) for s in employee_service.list_schedules(db, employee_id)]


@router.post("/{employee_id}/schedules", response_model=ScheduleOut, status_code=201)
def add_schedule(
    employee_id: int, data: ScheduleCreate, db: DbSession, actor: Actor
) -> ScheduleOut:
    return ScheduleOut.model_validate(employee_service.add_schedule(db, employee_id, data, actor))
