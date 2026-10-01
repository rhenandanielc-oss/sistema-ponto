from datetime import date

from fastapi import APIRouter, Depends, Response

from app.api.deps import Actor, DbSession, get_current_admin
from app.schemas.timekeeping import HolidayIn, HolidayOut, HolidayUpdate
from app.services import holiday_service

router = APIRouter(prefix="/holidays", tags=["feriados"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[HolidayOut])
def list_holidays(
    db: DbSession, date_from: date | None = None, date_to: date | None = None
) -> list[HolidayOut]:
    return [
        HolidayOut.model_validate(h) for h in holiday_service.list_holidays(db, date_from, date_to)
    ]


@router.post("", response_model=HolidayOut, status_code=201)
def create_holiday(data: HolidayIn, db: DbSession, actor: Actor) -> HolidayOut:
    return HolidayOut.model_validate(holiday_service.create(db, data, actor))


@router.patch("/{holiday_id}", response_model=HolidayOut)
def update_holiday(holiday_id: int, data: HolidayUpdate, db: DbSession, actor: Actor) -> HolidayOut:
    return HolidayOut.model_validate(holiday_service.update(db, holiday_id, data, actor))


@router.delete("/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, db: DbSession, actor: Actor) -> Response:
    holiday_service.delete(db, holiday_id, actor)
    return Response(status_code=204)
