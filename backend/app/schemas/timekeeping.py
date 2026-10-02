from datetime import date as Date
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.schemas.common import LocalDatetime, ORMModel

RecordType = Literal["ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT"]


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("não pode ficar vazio")
    return value


Reason = Annotated[str, Field(min_length=10, max_length=1000, description="Justificativa")]


# --- Feriados -----------------------------------------------------------------------------------


class HolidayIn(BaseModel):
    date: Date
    name: str = Field(max_length=200)
    recurring: bool = False

    _name = field_validator("name")(_strip_required)


class HolidayUpdate(BaseModel):
    date: Date | None = None
    name: str | None = Field(default=None, max_length=200)
    recurring: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)


class HolidayOut(ORMModel):
    id: int
    date: Date
    name: str
    recurring: bool


# --- Dispositivos -------------------------------------------------------------------------------


class DeviceIn(BaseModel):
    name: str = Field(max_length=100)

    _name = field_validator("name")(_strip_required)


class DeviceOut(ORMModel):
    id: int
    name: str
    is_active: bool
    last_seen_at: LocalDatetime | None
    created_at: LocalDatetime


class DeviceWithToken(DeviceOut):
    token: str = Field(description="Exibido somente agora. Configure-o no terminal.")


# --- Registros e ajustes ------------------------------------------------------------------------


class TimeRecordOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    type: RecordType
    recorded_at: LocalDatetime
    workday_date: Date
    source: Literal["KIOSK", "ADJUSTMENT"]
    device_id: int | None
    face_match_score: float | None
    voided_at: LocalDatetime | None
    created_at: LocalDatetime


class AdjustmentOut(ORMModel):
    id: int
    employee_id: int
    kind: Literal["ADD", "VOID"]
    record_id: int
    reason: str
    created_by_admin_id: int
    created_at: LocalDatetime


class TimeRecordDetail(TimeRecordOut):
    adjustments: list[AdjustmentOut]


class AddRecordAdjustment(BaseModel):
    kind: Literal["ADD"]
    employee_id: int
    type: RecordType
    recorded_at: datetime = Field(
        description="Horário da batida esquecida. Sem fuso, é interpretado no fuso da empresa."
    )
    workday_date: Date | None = Field(
        default=None, description="Dia de jornada. Padrão: data local de recorded_at"
    )
    reason: Reason

    @field_validator("recorded_at")
    @classmethod
    def _company_timezone(cls, value: datetime) -> datetime:
        # O administrador digita data e hora como vê no relógio da empresa.
        return value if value.tzinfo else value.replace(tzinfo=get_settings().tz)


class VoidRecordAdjustment(BaseModel):
    kind: Literal["VOID"]
    record_id: int
    reason: Reason


AdjustmentIn = Annotated[AddRecordAdjustment | VoidRecordAdjustment, Field(discriminator="kind")]


# --- Cálculo e banco de horas -------------------------------------------------------------------


class PunchOut(BaseModel):
    type: RecordType
    at: LocalDatetime


class DayOut(BaseModel):
    date: Date
    day_type: Literal["WORKDAY", "DAY_OFF", "HOLIDAY", "NOT_EMPLOYED"]
    status: Literal["OK", "ABSENT", "INCOMPLETE", "IN_PROGRESS", "FUTURE", "NONE"]
    flags: list[str]
    expected_start: LocalDatetime | None
    expected_end: LocalDatetime | None
    planned_minutes: int
    worked_minutes: int
    break_minutes: int
    late_minutes: int
    early_leave_minutes: int
    missing_minutes: int
    overtime_minutes: int
    night_minutes: int
    night_minutes_reduced: int
    balance_minutes: int
    counts_for_bank: bool
    punches: list[PunchOut]


class Totals(BaseModel):
    planned_minutes: int
    worked_minutes: int
    late_minutes: int
    early_leave_minutes: int
    missing_minutes: int
    overtime_minutes: int
    night_minutes: int
    balance_minutes: int
    absences: int
    incomplete_days: int


class HourBankEntryIn(BaseModel):
    entry_date: Date
    minutes: int = Field(description="Positivo = crédito, negativo = débito")
    kind: Literal["OPENING_BALANCE", "COMPENSATION", "PAYOUT", "CORRECTION"]
    reason: Reason

    @field_validator("minutes")
    @classmethod
    def _non_zero(cls, value: int) -> int:
        if value == 0 or abs(value) > 100_000:
            raise ValueError("informe minutos diferentes de zero")
        return value


class HourBankEntryOut(ORMModel):
    id: int
    employee_id: int
    entry_date: Date
    minutes: int
    kind: str
    reason: str
    created_by_admin_id: int
    created_at: LocalDatetime


class WorkdaysOut(BaseModel):
    employee_id: int
    date_from: Date
    date_to: Date
    days: list[DayOut]
    totals: Totals


class HourBankOut(WorkdaysOut):
    opening_balance_minutes: int = Field(description="Saldo acumulado antes de date_from")
    entries: list[HourBankEntryOut] = Field(description="Lançamentos manuais no período")
    entries_minutes: int
    closing_balance_minutes: int = Field(description="Saldo acumulado até date_to")


class HourBankSummaryItem(BaseModel):
    employee_id: int
    name: str
    registration_number: str
    status: Literal["ACTIVE", "INACTIVE"]
    opening_balance_minutes: int
    planned_minutes: int
    worked_minutes: int
    overtime_minutes: int
    missing_minutes: int
    period_balance_minutes: int = Field(description="Saldo dos dias do período (sem lançamentos)")
    entries_minutes: int
    closing_balance_minutes: int
    absences: int
    incomplete_days: int
