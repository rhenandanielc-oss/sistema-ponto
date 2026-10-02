"""Consulta da trilha de auditoria (somente leitura)."""

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, get_settings().tz)


def list_logs(
    db: Session,
    *,
    entity_type: str | None,
    entity_id: int | None,
    action: str | None,
    actor_admin_id: int | None,
    date_from: date | None,
    date_to: date | None,
    sort: Literal["occurred_at", "-occurred_at"],
    page: int,
    page_size: int,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    if entity_type is not None:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    if action is not None:
        # "employee." filtra todas as ações de funcionário; sem ponto final, busca exata.
        if action.endswith("."):
            query = query.where(AuditLog.action.startswith(action, autoescape=True))
        else:
            query = query.where(AuditLog.action == action)
    if actor_admin_id is not None:
        query = query.where(AuditLog.actor_admin_id == actor_admin_id)
    # Período inclusivo no fuso da empresa: [início de date_from, início do dia seguinte a date_to).
    if date_from is not None:
        query = query.where(AuditLog.occurred_at >= _start_of(date_from))
    if date_to is not None:
        query = query.where(AuditLog.occurred_at < _start_of(date_to + timedelta(days=1)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = AuditLog.occurred_at.desc() if sort.startswith("-") else AuditLog.occurred_at.asc()
    id_order = AuditLog.id.desc() if sort.startswith("-") else AuditLog.id.asc()
    items = db.scalars(
        query.order_by(order, id_order).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(items), total
