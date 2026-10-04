from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import Actor, DbSession, get_current_admin
from app.calculation.payroll import period_containing
from app.core.clock import today_local
from app.schemas.consumption import (
    ConsumptionCancelIn,
    ConsumptionEntryIn,
    ConsumptionEntryOut,
    ConsumptionItemIn,
    ConsumptionItemOut,
    ConsumptionItemUpdate,
    ConsumptionList,
)
from app.services import consumption_service, employee_service

router = APIRouter(tags=["consumo"], dependencies=[Depends(get_current_admin)])


@router.get("/consumption-items", response_model=list[ConsumptionItemOut])
def list_items(
    db: DbSession, include_inactive: Annotated[bool, Query()] = True
) -> list[ConsumptionItemOut]:
    return [
        ConsumptionItemOut.model_validate(i)
        for i in consumption_service.list_items(db, include_inactive)
    ]


@router.post("/consumption-items", response_model=ConsumptionItemOut, status_code=201)
def create_item(data: ConsumptionItemIn, db: DbSession, actor: Actor) -> ConsumptionItemOut:
    return ConsumptionItemOut.model_validate(consumption_service.create_item(db, data, actor))


@router.patch("/consumption-items/{item_id}", response_model=ConsumptionItemOut)
def update_item(
    item_id: int, data: ConsumptionItemUpdate, db: DbSession, actor: Actor
) -> ConsumptionItemOut:
    return ConsumptionItemOut.model_validate(
        consumption_service.update_item(db, item_id, data, actor)
    )


@router.get("/employees/{employee_id}/consumption", response_model=ConsumptionList)
def list_entries(
    employee_id: int,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ConsumptionList:
    """Padrão: o ciclo de pagamento atual do funcionário."""
    if date_from is None or date_to is None:
        period = period_containing(today_local(), employee_service.get(db, employee_id).payday)
        date_from, date_to = date_from or period.start, date_to or period.end
    entries = consumption_service.list_entries(db, employee_id, date_from, date_to)
    return ConsumptionList(
        items=[ConsumptionEntryOut.model_validate(e) for e in entries],
        total_cents=sum(e.total_cents for e in entries if e.canceled_at is None),
    )


@router.post(
    "/employees/{employee_id}/consumption", response_model=ConsumptionEntryOut, status_code=201
)
def add_entry(
    employee_id: int, data: ConsumptionEntryIn, db: DbSession, actor: Actor
) -> ConsumptionEntryOut:
    return ConsumptionEntryOut.model_validate(
        consumption_service.add_entry(db, employee_id, data, actor)
    )


@router.post("/consumption/{entry_id}/cancel", response_model=ConsumptionEntryOut)
def cancel_entry(
    entry_id: int, data: ConsumptionCancelIn, db: DbSession, actor: Actor
) -> ConsumptionEntryOut:
    return ConsumptionEntryOut.model_validate(
        consumption_service.cancel_entry(db, entry_id, data.reason, actor)
    )
