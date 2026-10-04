"""Consumo do funcionário (BUSINESS-RULES.md §12)."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import now_utc, today_local
from app.core.errors import AppError, conflict, not_found
from app.models import ConsumptionEntry, ConsumptionItem
from app.schemas.consumption import ConsumptionEntryIn, ConsumptionItemIn, ConsumptionItemUpdate
from app.services import audit, employee_service


def _item_snapshot(item: ConsumptionItem) -> dict[str, object]:
    return {"name": item.name, "price_cents": item.price_cents, "is_active": item.is_active}


def _require_admin(actor: audit.Actor) -> int:
    if actor.admin_id is None:
        raise AppError(403, "FORBIDDEN", "Somente administradores lançam consumo.")
    return actor.admin_id


def _commit_item(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("CONFLICT", "Já existe um item com esse nome.") from exc


# --- Itens --------------------------------------------------------------------------------------


def list_items(db: Session, include_inactive: bool = True) -> list[ConsumptionItem]:
    query = select(ConsumptionItem).order_by(func.lower(ConsumptionItem.name))
    if not include_inactive:
        query = query.where(ConsumptionItem.is_active.is_(True))
    return list(db.scalars(query).all())


def get_item(db: Session, item_id: int) -> ConsumptionItem:
    item = db.get(ConsumptionItem, item_id)
    if item is None:
        raise not_found("Item não encontrado.")
    return item


def create_item(db: Session, data: ConsumptionItemIn, actor: audit.Actor) -> ConsumptionItem:
    item = ConsumptionItem(name=data.name.strip(), price_cents=data.price_cents)
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("CONFLICT", "Já existe um item com esse nome.") from exc
    audit.record(
        db,
        actor=actor,
        action="consumption_item.create",
        entity_type="consumption_item",
        entity_id=item.id,
        after=_item_snapshot(item),
    )
    _commit_item(db)
    return item


def update_item(
    db: Session, item_id: int, data: ConsumptionItemUpdate, actor: audit.Actor
) -> ConsumptionItem:
    item = get_item(db, item_id)
    before = _item_snapshot(item)
    if data.name is not None:
        item.name = data.name.strip()
    if data.price_cents is not None:
        item.price_cents = data.price_cents  # lançamentos antigos guardam o preço da época
    if data.is_active is not None:
        item.is_active = data.is_active
    audit.record(
        db,
        actor=actor,
        action="consumption_item.update",
        entity_type="consumption_item",
        entity_id=item.id,
        before=before,
        after=_item_snapshot(item),
    )
    _commit_item(db)
    return item


# --- Lançamentos --------------------------------------------------------------------------------


def add_entry(
    db: Session, employee_id: int, data: ConsumptionEntryIn, actor: audit.Actor
) -> ConsumptionEntry:
    admin_id = _require_admin(actor)
    employee_service.get(db, employee_id)
    if data.item_id is not None:
        item = get_item(db, data.item_id)
        if not item.is_active:
            raise conflict("CONFLICT", "Item desativado.")
        description, unit_price = item.name, item.price_cents
    else:
        assert data.description is not None and data.unit_price_cents is not None
        description, unit_price = data.description.strip(), data.unit_price_cents
    entry = ConsumptionEntry(
        employee_id=employee_id,
        entry_date=data.entry_date or today_local(),
        item_id=data.item_id,
        description=description,
        quantity=data.quantity,
        unit_price_cents=unit_price,
        created_by_admin_id=admin_id,
    )
    db.add(entry)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="consumption.create",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "entry_id": entry.id,
            "entry_date": entry.entry_date,
            "description": description,
            "quantity": entry.quantity,
            "unit_price_cents": unit_price,
            "total_cents": entry.total_cents,
        },
    )
    db.commit()
    return entry


def cancel_entry(db: Session, entry_id: int, reason: str, actor: audit.Actor) -> ConsumptionEntry:
    admin_id = _require_admin(actor)
    entry = db.scalar(
        select(ConsumptionEntry).where(ConsumptionEntry.id == entry_id).with_for_update()
    )
    if entry is None:
        raise not_found("Lançamento não encontrado.")
    if entry.canceled_at is not None:
        raise conflict("CONFLICT", "Lançamento já cancelado.")
    entry.canceled_at = now_utc()
    entry.canceled_by_admin_id = admin_id
    entry.cancel_reason = reason
    audit.record(
        db,
        actor=actor,
        action="consumption.cancel",
        entity_type="employee",
        entity_id=entry.employee_id,
        after={"entry_id": entry.id, "total_cents": entry.total_cents, "reason": reason},
    )
    db.commit()
    return entry


def list_entries(
    db: Session, employee_id: int, date_from: date, date_to: date
) -> list[ConsumptionEntry]:
    employee_service.get(db, employee_id)
    return list(
        db.scalars(
            select(ConsumptionEntry)
            .where(
                ConsumptionEntry.employee_id == employee_id,
                ConsumptionEntry.entry_date >= date_from,
                ConsumptionEntry.entry_date <= date_to,
            )
            .order_by(ConsumptionEntry.entry_date, ConsumptionEntry.id)
        ).all()
    )


def total_cents(db: Session, employee_id: int, date_from: date, date_to: date) -> int:
    """Soma dos lançamentos não cancelados entre as datas (inclusive)."""
    total = db.scalar(
        select(
            func.coalesce(
                func.sum(ConsumptionEntry.quantity * ConsumptionEntry.unit_price_cents), 0
            )
        ).where(
            ConsumptionEntry.employee_id == employee_id,
            ConsumptionEntry.canceled_at.is_(None),
            ConsumptionEntry.entry_date >= date_from,
            ConsumptionEntry.entry_date <= date_to,
        )
    )
    return int(total or 0)
