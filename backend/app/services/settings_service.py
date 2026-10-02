"""Parâmetros configuráveis da empresa (tabela `settings`). Valores ausentes usam o padrão."""

from datetime import time, timedelta
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation.workday import Rules
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Setting
from app.services import audit


class CompanySettings(BaseModel):
    tolerance_per_mark_minutes: int = Field(default=5, ge=0, le=60)
    tolerance_daily_minutes: int = Field(default=10, ge=0, le=120)
    min_minutes_between_records: int = Field(default=2, ge=0, le=60)
    max_shift_hours: int = Field(default=16, ge=1, le=24)
    early_entry_window_hours: int = Field(default=4, ge=0, le=12)
    night_start: time = time(22)
    night_end: time = time(5)
    kiosk_hour_bank_screen_seconds: int = Field(default=30, ge=5, le=600)


class CompanySettingsUpdate(BaseModel):
    tolerance_per_mark_minutes: int | None = Field(default=None, ge=0, le=60)
    tolerance_daily_minutes: int | None = Field(default=None, ge=0, le=120)
    min_minutes_between_records: int | None = Field(default=None, ge=0, le=60)
    max_shift_hours: int | None = Field(default=None, ge=1, le=24)
    early_entry_window_hours: int | None = Field(default=None, ge=0, le=12)
    night_start: time | None = None
    night_end: time | None = None
    kiosk_hour_bank_screen_seconds: int | None = Field(default=None, ge=5, le=600)


def load(db: Session) -> CompanySettings:
    stored = {row.key: row.value for row in db.scalars(select(Setting)).all()}
    known = {k: v for k, v in stored.items() if k in CompanySettings.model_fields}
    try:
        return CompanySettings.model_validate(known)
    except ValidationError:
        # Valor inválido gravado manualmente no banco: usa os padrões em vez de derrubar o cálculo.
        return CompanySettings()


def rules(settings: CompanySettings) -> Rules:
    return Rules(
        tz=get_settings().tz,
        tolerance_per_mark_minutes=settings.tolerance_per_mark_minutes,
        tolerance_daily_minutes=settings.tolerance_daily_minutes,
        max_shift=timedelta(hours=settings.max_shift_hours),
        night_start=settings.night_start,
        night_end=settings.night_end,
    )


def update(db: Session, data: CompanySettingsUpdate, actor: audit.Actor) -> CompanySettings:
    changes = data.model_dump(exclude_unset=True, mode="json")
    if any(v is None for v in changes.values()):
        raise AppError(422, "VALIDATION_ERROR", "Configurações não podem ficar vazias.")
    before = load(db).model_dump(mode="json")
    for key, value in changes.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.flush()
    after = load(db).model_dump(mode="json")
    audit.record(
        db,
        actor=actor,
        action="settings.update",
        entity_type="settings",
        before=_diff(before, after),
        after=_diff(after, before),
    )
    db.commit()
    return load(db)


def _diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in a.items() if b.get(k) != v}
