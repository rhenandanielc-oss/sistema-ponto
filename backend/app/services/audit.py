from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.request_context import current_request
from app.models import AuditLog

ActorType = Literal["ADMIN", "DEVICE", "EMPLOYEE_FACE", "SYSTEM", "ANONYMOUS"]


@dataclass(frozen=True)
class Actor:
    type: ActorType
    admin_id: int | None = None
    device_id: int | None = None
    employee_id: int | None = None


SYSTEM = Actor("SYSTEM")
ANONYMOUS = Actor("ANONYMOUS")


def admin_actor(admin_id: int) -> Actor:
    return Actor("ADMIN", admin_id=admin_id)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def record(
    db: Session,
    *,
    actor: Actor,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Adiciona uma entrada de auditoria à transação atual (não faz commit).

    Nunca passe senhas, tokens, imagens ou templates biométricos em `before`/`after`.
    """
    req = current_request()
    db.add(
        AuditLog(
            actor_type=actor.type,
            actor_admin_id=actor.admin_id,
            actor_device_id=actor.device_id,
            actor_employee_id=actor.employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=_jsonable(before) if before is not None else None,
            after=_jsonable(after) if after is not None else None,
            ip=req.ip if req else None,
            user_agent=req.user_agent if req else None,
            request_id=req.request_id if req else None,
        )
    )
