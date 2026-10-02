from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import Actor, DbSession, PageParams, get_current_admin
from app.models import TimeRecord
from app.schemas.common import Page
from app.schemas.timekeeping import (
    AddRecordAdjustment,
    AdjustmentIn,
    AdjustmentOut,
    RecordType,
    TimeRecordDetail,
    TimeRecordOut,
)
from app.services import record_service

router = APIRouter(
    prefix="/time-records", tags=["registros de ponto"], dependencies=[Depends(get_current_admin)]
)


def _out(record: TimeRecord, employee_name: str) -> TimeRecordOut:
    return TimeRecordOut.model_validate(
        {**TimeRecordOut.model_validate(record).model_dump(), "employee_name": employee_name}
    )


@router.get("", response_model=Page[TimeRecordOut])
def list_records(
    db: DbSession,
    pagination: PageParams,
    employee_id: int | None = None,
    date_from: Annotated[
        date | None, Query(description="Dia de jornada inicial (inclusivo)")
    ] = None,
    date_to: Annotated[date | None, Query(description="Dia de jornada final (inclusivo)")] = None,
    type: RecordType | None = None,
    source: Literal["KIOSK", "ADJUSTMENT"] | None = None,
    device_id: int | None = None,
    include_voided: bool = False,
    sort: Literal["recorded_at", "-recorded_at"] = "-recorded_at",
) -> Page[TimeRecordOut]:
    rows, total = record_service.list_records(
        db,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        record_type=type,
        source=source,
        device_id=device_id,
        include_voided=include_voided,
        sort=sort,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(
        items=[_out(r, name) for r, name in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/adjustments", response_model=Page[AdjustmentOut])
def list_adjustments(
    db: DbSession, pagination: PageParams, employee_id: int | None = None
) -> Page[AdjustmentOut]:
    items, total = record_service.list_adjustments(
        db, employee_id, pagination.page, pagination.page_size
    )
    return Page(
        items=[AdjustmentOut.model_validate(a) for a in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/adjustments", response_model=AdjustmentOut, status_code=201)
def create_adjustment(data: AdjustmentIn, db: DbSession, actor: Actor) -> AdjustmentOut:
    """Inclui uma batida esquecida (ADD) ou anula uma batida errada (VOID), com justificativa."""
    if isinstance(data, AddRecordAdjustment):
        adjustment = record_service.add_record(db, data, actor)
    else:
        adjustment = record_service.void_record(db, data, actor)
    return AdjustmentOut.model_validate(adjustment)


@router.get("/{record_id}", response_model=TimeRecordDetail)
def get_record(record_id: int, db: DbSession) -> TimeRecordDetail:
    record, name = record_service.get_detail(db, record_id)
    return TimeRecordDetail.model_validate(
        {
            **_out(record, name).model_dump(),
            "adjustments": [AdjustmentOut.model_validate(a) for a in record.adjustments],
        }
    )
