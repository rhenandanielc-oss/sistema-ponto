"""Endpoints do terminal de ponto (token de dispositivo). Nenhum recebe id de funcionário."""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.biometrics import read_image
from app.api.deps import CurrentDevice, DbSession
from app.biometrics.engine import FaceEngine, get_face_engine
from app.calculation.payroll import period_containing
from app.calculation.workday import DayResult
from app.core.clock import now_utc, today_local
from app.core.rate_limit import rate_limit
from app.schemas.common import LocalDatetime
from app.services import (
    audit,
    biometric_service,
    consumption_service,
    device_service,
    hour_bank_service,
    location_service,
    record_service,
    settings_service,
)

# O limite vem antes da autenticação: tokens inválidos também contam.
router = APIRouter(
    prefix="/kiosk", tags=["kiosk"], dependencies=[Depends(rate_limit("kiosk", limit=120))]
)

Engine = Annotated[FaceEngine, Depends(get_face_engine)]
RecordType = Literal["ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT"]


class PingOut(BaseModel):
    device: str
    server_time: LocalDatetime
    require_location: bool = Field(description="O terminal deve enviar a localização do celular")


@router.get("/ping", response_model=PingOut)
def ping(device: CurrentDevice) -> PingOut:
    """Confirma que o terminal está autorizado e devolve o horário do servidor para exibição."""
    return PingOut(
        device=device.name, server_time=now_utc(), require_location=device.require_location
    )


class ActivateIn(BaseModel):
    code: str = Field(min_length=10, max_length=200)


class ActivateOut(BaseModel):
    token: str = Field(description="Token do terminal: o navegador guarda e usa nas próximas vezes")
    device: str


@router.post(
    "/activate",
    response_model=ActivateOut,
    dependencies=[Depends(rate_limit("kiosk-activate", limit=10))],
)
def activate(data: ActivateIn, db: DbSession) -> ActivateOut:
    """Ativa o terminal com o código de uso único do link (sem digitar a chave)."""
    device, token = device_service.activate_with_code(db, data.code)
    return ActivateOut(token=token, device=device.name)


class IdentifyOut(BaseModel):
    identification_token: str
    expires_in: int
    employee_name: str
    workday_date: date
    allowed_types: list[RecordType] = Field(
        description="Botões de batida que devem ficar habilitados"
    )
    hour_bank_screen_seconds: int


@router.post("/identify", response_model=IdentifyOut)
async def identify(
    device: CurrentDevice,
    db: DbSession,
    engine: Engine,
    image: Annotated[UploadFile, File(description="Um quadro da câmera (JPEG/PNG, até 1 MB)")],
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    accuracy_m: Annotated[float | None, Form()] = None,
) -> IdentifyOut:
    """Reconhece o funcionário pelo rosto. A imagem é descartada ao fim da requisição."""
    location_service.check(db, device, latitude, longitude, accuracy_m)
    data = await read_image(image)
    result = biometric_service.identify(db, data, engine, device)
    workday, allowed = record_service.allowed_types(db, result.employee.id)
    return IdentifyOut(
        identification_token=result.token,
        expires_in=int((result.expires_at - now_utc()).total_seconds()),
        employee_name=result.employee.name,
        workday_date=workday,
        allowed_types=list(allowed),
        hour_bank_screen_seconds=settings_service.load(db).kiosk_hour_bank_screen_seconds,
    )


class KioskRecordIn(BaseModel):
    identification_token: str = Field(min_length=10, max_length=200)
    type: RecordType
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None


class KioskRecordOut(BaseModel):
    employee_name: str
    type: RecordType
    recorded_at: LocalDatetime
    workday_date: date


@router.post("/records", response_model=KioskRecordOut, status_code=201)
def create_record(data: KioskRecordIn, device: CurrentDevice, db: DbSession) -> KioskRecordOut:
    """Registra a batida escolhida. O horário é o do servidor; o token é consumido."""
    location_service.check(db, device, data.latitude, data.longitude, data.accuracy_m)
    identification = biometric_service.resolve_token(
        db, data.identification_token, device, consume=True
    )
    record = record_service.create_record(
        db,
        employee_id=identification.employee_id,
        record_type=data.type,
        actor=audit.Actor("DEVICE", device_id=device.id, employee_id=identification.employee_id),
        device_id=device.id,
        face_match_score=identification.score,
    )
    employee = biometric_service.get_employee_or_404(db, identification.employee_id)
    return KioskRecordOut(
        employee_name=employee.name,
        type=data.type,
        recorded_at=record.recorded_at,
        workday_date=record.workday_date,
    )


class KioskHourBankIn(BaseModel):
    identification_token: str = Field(min_length=10, max_length=200)


class KioskDay(BaseModel):
    date: date
    status: str
    planned_minutes: int = 0
    worked_minutes: int
    balance_minutes: int
    counts_for_bank: bool
    entry: LocalDatetime | None = Field(default=None, description="Entrada")
    lunch_exit: LocalDatetime | None = Field(default=None, description="Saída para almoço")
    lunch_return: LocalDatetime | None = Field(default=None, description="Retorno do almoço")
    exit: LocalDatetime | None = Field(default=None, description="Saída")


def _kiosk_day(d: DayResult) -> KioskDay:
    times = {p.type: p.at for p in d.punches}
    return KioskDay(
        date=d.day,
        status=d.status,
        planned_minutes=d.planned_minutes,
        worked_minutes=d.worked_minutes,
        balance_minutes=d.balance_minutes,
        counts_for_bank=d.counts_for_bank,
        entry=times.get("ENTRY"),
        lunch_exit=times.get("LUNCH_EXIT"),
        lunch_return=times.get("LUNCH_RETURN"),
        exit=times.get("EXIT"),
    )


class KioskHourBankOut(BaseModel):
    employee_name: str
    balance_minutes: int = Field(description="Saldo acumulado do banco de horas até hoje")
    month_start: date
    month_overtime_minutes: int
    month_missing_minutes: int
    month_absences: int
    month_worked_minutes: int = Field(default=0, description="Horas trabalhadas no mês até agora")
    month_balance_minutes: int = Field(default=0, description="Extras − faltantes do mês até agora")
    week_start: date | None = Field(default=None, description="Segunda-feira da semana atual")
    week: list[KioskDay] = Field(
        default=[], description="Dias da semana atual até hoje, com horários"
    )
    week_worked_minutes: int = 0
    week_balance_minutes: int = 0
    pay_period_start: date
    pay_period_end: date
    pay_period_overtime_minutes: int
    pay_period_missing_minutes: int
    pay_period_consumption_cents: int = Field(
        description="Consumo do funcionário no ciclo (descontado no pagamento)"
    )
    days: list[KioskDay]
    screen_seconds: int


@router.post("/hour-bank", response_model=KioskHourBankOut)
def own_hour_bank(data: KioskHourBankIn, device: CurrentDevice, db: DbSession) -> KioskHourBankOut:
    """Banco de horas do funcionário reconhecido — e somente dele (BUSINESS-RULES.md §9.1)."""
    identification = biometric_service.resolve_token(
        db, data.identification_token, device, consume=False
    )
    employee = biometric_service.get_employee_or_404(db, identification.employee_id)
    today = today_local()
    month_start = today.replace(day=1)
    bank = hour_bank_service.hour_bank(db, employee.id, month_start, today)
    period = period_containing(today, employee.payday)
    pay_totals = hour_bank_service.period_totals(db, employee, period.start, period.end)
    week_start = today - timedelta(days=today.weekday())
    week_days, week_totals = hour_bank_service.workdays(db, employee.id, week_start, today)
    audit.record(
        db,
        actor=audit.Actor("DEVICE", device_id=device.id, employee_id=employee.id),
        action="kiosk.hour_bank_viewed",
        entity_type="employee",
        entity_id=employee.id,
    )
    db.commit()
    return KioskHourBankOut(
        employee_name=employee.name,
        balance_minutes=bank.closing_balance_minutes,
        month_start=month_start,
        month_overtime_minutes=bank.totals.overtime_minutes,
        month_missing_minutes=bank.totals.missing_minutes,
        month_absences=bank.totals.absences,
        month_worked_minutes=bank.totals.worked_minutes,
        month_balance_minutes=bank.totals.balance_minutes,
        week_start=week_start,
        week=[_kiosk_day(d) for d in week_days],
        week_worked_minutes=week_totals.worked_minutes,
        week_balance_minutes=week_totals.balance_minutes,
        pay_period_start=period.start,
        pay_period_end=period.end,
        pay_period_overtime_minutes=pay_totals.overtime_minutes,
        pay_period_missing_minutes=pay_totals.missing_minutes,
        pay_period_consumption_cents=consumption_service.total_cents(
            db, employee.id, period.start, period.end
        ),
        days=[
            _kiosk_day(d)
            for d in bank.days
            if d.day <= today and d.day >= today - timedelta(days=31)
        ],
        screen_seconds=settings_service.load(db).kiosk_hour_bank_screen_seconds,
    )
