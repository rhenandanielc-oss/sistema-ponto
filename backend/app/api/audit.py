from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, PageParams, get_current_admin
from app.schemas.common import LocalDatetime, ORMModel, Page
from app.services import audit_query

router = APIRouter(
    prefix="/audit-logs", tags=["auditoria"], dependencies=[Depends(get_current_admin)]
)


class AuditLogOut(ORMModel):
    id: int
    occurred_at: LocalDatetime
    actor_type: str
    actor_admin_id: int | None
    actor_device_id: int | None
    actor_employee_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    request_id: str | None


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: DbSession,
    pagination: PageParams,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: Annotated[
        str | None, Query(description='Ação exata, ou prefixo terminado em "." (ex.: "employee.")')
    ] = None,
    actor_admin_id: int | None = None,
    date_from: Annotated[date | None, Query(description="Data inicial (inclusiva)")] = None,
    date_to: Annotated[date | None, Query(description="Data final (inclusiva)")] = None,
    sort: Literal["occurred_at", "-occurred_at"] = "-occurred_at",
) -> Page[AuditLogOut]:
    items, total = audit_query.list_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_admin_id=actor_admin_id,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(
        items=[AuditLogOut.model_validate(i) for i in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
