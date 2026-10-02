from collections.abc import Sequence
from datetime import date

from sqlalchemy import extract, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.models import Holiday
from app.schemas.timekeeping import HolidayIn, HolidayUpdate
from app.services import audit


def _snapshot(h: Holiday) -> dict[str, object]:
    return {"date": h.date, "name": h.name, "recurring": h.recurring}


def _check_duplicate(db: Session, day: date, recurring: bool, exclude_id: int | None) -> None:
    query = select(Holiday.id)
    if recurring:
        query = query.where(
            Holiday.recurring.is_(True),
            extract("month", Holiday.date) == day.month,
            extract("day", Holiday.date) == day.day,
        )
    else:
        query = query.where(Holiday.recurring.is_(False), Holiday.date == day)
    if exclude_id is not None:
        query = query.where(Holiday.id != exclude_id)
    if db.scalar(query) is not None:
        raise conflict("CONFLICT", "Já existe um feriado nesta data.")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("CONFLICT", "Já existe um feriado nesta data.") from exc


def list_holidays(db: Session, date_from: date | None, date_to: date | None) -> list[Holiday]:
    """Feriados no período. Recorrentes aparecem sempre (valem todo ano)."""
    query = select(Holiday).order_by(Holiday.date, Holiday.id)
    items = db.scalars(query).all()
    return [
        h
        for h in items
        if h.recurring
        or ((date_from is None or h.date >= date_from) and (date_to is None or h.date <= date_to))
    ]


def holiday_dates(db: Session, date_from: date, date_to: date) -> set[date]:
    """Datas de feriado entre `date_from` e `date_to` (inclusive), expandindo os recorrentes."""
    return expand(db.scalars(select(Holiday)).all(), date_from, date_to)


def expand(holidays: Sequence[Holiday], date_from: date, date_to: date) -> set[date]:
    result: set[date] = set()
    for h in holidays:
        if not h.recurring:
            if date_from <= h.date <= date_to:
                result.add(h.date)
            continue
        for year in range(date_from.year, date_to.year + 1):
            try:
                occurrence = h.date.replace(year=year)
            except ValueError:  # 29/02 em ano não bissexto
                continue
            if date_from <= occurrence <= date_to:
                result.add(occurrence)
    return result


def get(db: Session, holiday_id: int) -> Holiday:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None:
        raise not_found("Feriado não encontrado.")
    return holiday


def create(db: Session, data: HolidayIn, actor: audit.Actor) -> Holiday:
    _check_duplicate(db, data.date, data.recurring, None)
    holiday = Holiday(date=data.date, name=data.name, recurring=data.recurring)
    db.add(holiday)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="holiday.create",
        entity_type="holiday",
        entity_id=holiday.id,
        after=_snapshot(holiday),
    )
    _commit(db)
    return holiday


def update(db: Session, holiday_id: int, data: HolidayUpdate, actor: audit.Actor) -> Holiday:
    holiday = get(db, holiday_id)
    before = _snapshot(holiday)
    changes = data.model_dump(exclude_unset=True)
    new_date = changes.get("date", holiday.date)
    new_recurring = changes.get("recurring", holiday.recurring)
    _check_duplicate(db, new_date, new_recurring, holiday.id)
    for key, value in changes.items():
        if value is not None:
            setattr(holiday, key, value)
    audit.record(
        db,
        actor=actor,
        action="holiday.update",
        entity_type="holiday",
        entity_id=holiday.id,
        before=before,
        after=_snapshot(holiday),
    )
    _commit(db)
    return holiday


def delete(db: Session, holiday_id: int, actor: audit.Actor) -> None:
    holiday = get(db, holiday_id)
    audit.record(
        db,
        actor=actor,
        action="holiday.delete",
        entity_type="holiday",
        entity_id=holiday.id,
        before=_snapshot(holiday),
    )
    db.delete(holiday)
    db.commit()
