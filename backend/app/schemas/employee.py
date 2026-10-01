import re
from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.calculation.schedule import DaySchedule, ScheduleError, planned_minutes, validate_week
from app.schemas.common import ORMModel


def normalize_cpf(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValueError("CPF inválido")
    for size in (9, 10):
        total = sum(int(d) * (size + 1 - i) for i, d in enumerate(digits[:size]))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            raise ValueError("CPF inválido")
    return digits


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("não pode ficar vazio")
    return value


class ScheduleDayIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = segunda … 6 = domingo")
    start_time: time
    lunch_start: time | None = None
    lunch_end: time | None = None
    end_time: time

    def to_domain(self) -> DaySchedule:
        return DaySchedule(
            weekday=self.weekday,
            start_time=self.start_time,
            end_time=self.end_time,
            lunch_start=self.lunch_start,
            lunch_end=self.lunch_end,
        )


class ScheduleDaysIn(BaseModel):
    days: list[ScheduleDayIn] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def _validate_week(self) -> "ScheduleDaysIn":
        try:
            validate_week([d.to_domain() for d in self.days])
        except ScheduleError as exc:
            raise ValueError(str(exc)) from exc
        return self


class ScheduleCreate(ScheduleDaysIn):
    valid_from: date


class ScheduleDayOut(ORMModel):
    weekday: int
    start_time: time
    lunch_start: time | None
    lunch_end: time | None
    end_time: time
    planned_minutes: int = 0

    @model_validator(mode="before")
    @classmethod
    def _compute_planned(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        day = DaySchedule(
            weekday=data.weekday,
            start_time=data.start_time,
            end_time=data.end_time,
            lunch_start=data.lunch_start,
            lunch_end=data.lunch_end,
        )
        return {
            "weekday": data.weekday,
            "start_time": data.start_time,
            "lunch_start": data.lunch_start,
            "lunch_end": data.lunch_end,
            "end_time": data.end_time,
            "planned_minutes": planned_minutes(day),
        }


class ScheduleOut(ORMModel):
    id: int
    valid_from: date
    valid_to: date | None
    days: list[ScheduleDayOut]
    created_at: datetime


class EmployeeCreate(BaseModel):
    name: str = Field(max_length=200)
    registration_number: str = Field(max_length=50)
    cpf: str | None = None
    hire_date: date
    schedule: ScheduleDaysIn

    _name = field_validator("name", "registration_number")(_strip_required)
    _cpf = field_validator("cpf")(normalize_cpf)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    registration_number: str | None = Field(default=None, max_length=50)
    cpf: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None

    @field_validator("name", "registration_number")
    @classmethod
    def _required_if_present(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)

    _cpf = field_validator("cpf")(normalize_cpf)


class EmployeeOut(ORMModel):
    id: int
    registration_number: str
    name: str
    cpf: str | None
    hire_date: date
    termination_date: date | None
    status: Literal["ACTIVE", "INACTIVE"]
    created_at: datetime
    updated_at: datetime


class EmployeeDetail(EmployeeOut):
    current_schedule: ScheduleOut | None


class AuditEntryOut(ORMModel):
    id: int
    occurred_at: datetime
    action: str
    actor_type: str
    actor_admin_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
