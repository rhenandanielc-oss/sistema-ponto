import re
import unicodedata
from datetime import date, time
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.calculation.schedule import (
    DEFAULT_LUNCH_MINUTES,
    MAX_SHIFT_MINUTES,
    DaySchedule,
    ScheduleError,
    planned_minutes,
    validate_week,
)
from app.schemas.common import LocalDatetime, ORMModel

DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]  # segunda a sexta


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


_WEEKDAY_PREFIXES = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")


def parse_weekday(value: Any) -> Any:
    """Aceita o dia como número (0 = segunda … 6 = domingo) ou nome ("segunda", "sáb", ...)."""
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKD", value.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    if text.isdigit():
        return int(text)
    for index, prefix in enumerate(_WEEKDAY_PREFIXES):
        if text.startswith(prefix):
            return index
    raise ValueError(f"dia da semana inválido: {value!r} (use segunda, terça, … domingo)")


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("não pode ficar vazio")
    return value


class ScheduleDayIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = segunda … 6 = domingo")
    start_time: time = Field(description="Entrada prevista, ex.: 08:00")
    end_time: time = Field(
        description="Saída prevista, ex.: 16:00 (menor que a entrada = dia seguinte)"
    )
    lunch_minutes: int = Field(
        default=DEFAULT_LUNCH_MINUTES, ge=0, le=MAX_SHIFT_MINUTES, description="Duração do almoço"
    )

    _weekday = field_validator("weekday", mode="before")(parse_weekday)

    def to_domain(self) -> DaySchedule:
        return DaySchedule(
            weekday=self.weekday,
            start_time=self.start_time,
            end_time=self.end_time,
            lunch_minutes=self.lunch_minutes,
        )


class ScheduleDaysIn(BaseModel):
    """Horário fixo. Aceita a forma simples ou dia a dia.

    Forma simples (mesmo horário em vários dias):
        {"start_time": "08:00", "end_time": "16:00", "lunch_minutes": 60,
         "weekdays": ["segunda", "terça", "quarta", "quinta", "sexta", "sábado"]}
    Dia a dia:
        {"days": [{"weekday": 0, "start_time": "08:00", "end_time": "16:00"}, ...]}
    """

    days: list[ScheduleDayIn] = Field(min_length=1, max_length=7)

    @model_validator(mode="before")
    @classmethod
    def _expand_simple_form(cls, data: Any) -> Any:
        if isinstance(data, dict) and "days" not in data and "start_time" in data:
            weekdays = data.get("weekdays", DEFAULT_WEEKDAYS)
            if not isinstance(weekdays, list) or not weekdays:
                raise ValueError('weekdays deve ser uma lista de dias, ex.: ["segunda", "sábado"]')
            common = {k: data[k] for k in ("start_time", "end_time", "lunch_minutes") if k in data}
            rest = {
                k: v
                for k, v in data.items()
                if k not in ("start_time", "end_time", "lunch_minutes", "weekdays")
            }
            return {**rest, "days": [{"weekday": w, **common} for w in weekdays]}
        return data

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
    end_time: time
    lunch_minutes: int
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
            lunch_minutes=data.lunch_minutes,
        )
        return {
            "weekday": data.weekday,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "lunch_minutes": data.lunch_minutes,
            "planned_minutes": planned_minutes(day),
        }


class ScheduleOut(ORMModel):
    id: int
    valid_from: date
    valid_to: date | None
    days: list[ScheduleDayOut]
    created_at: LocalDatetime


class EmployeeCreate(BaseModel):
    name: str = Field(max_length=200)
    registration_number: str = Field(max_length=50)
    cpf: str | None = None
    hire_date: date
    payday: int = Field(ge=1, le=31, description="Dia do mês do pagamento (31 = último dia)")
    schedule: ScheduleDaysIn

    _name = field_validator("name", "registration_number")(_strip_required)
    _cpf = field_validator("cpf")(normalize_cpf)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    registration_number: str | None = Field(default=None, max_length=50)
    cpf: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    payday: int | None = Field(default=None, ge=1, le=31)

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
    payday: int
    created_at: LocalDatetime
    updated_at: LocalDatetime


class EmployeeDetail(EmployeeOut):
    current_schedule: ScheduleOut | None


class AuditEntryOut(ORMModel):
    id: int
    occurred_at: LocalDatetime
    action: str
    actor_type: str
    actor_admin_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
