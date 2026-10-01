from fastapi import APIRouter, Depends

from app.api.deps import Actor, DbSession, PageParams, get_current_admin
from app.schemas.admin import AdminCreate, AdminUpdate
from app.schemas.auth import AdminOut
from app.schemas.common import Page
from app.services import admin_service

router = APIRouter(
    prefix="/admins", tags=["administradores"], dependencies=[Depends(get_current_admin)]
)


@router.get("", response_model=Page[AdminOut])
def list_admins(db: DbSession, pagination: PageParams) -> Page[AdminOut]:
    items, total = admin_service.list_admins(db, pagination.page, pagination.page_size)
    return Page(
        items=[AdminOut.model_validate(a) for a in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("", response_model=AdminOut, status_code=201)
def create_admin(data: AdminCreate, db: DbSession, actor: Actor) -> AdminOut:
    return AdminOut.model_validate(admin_service.create(db, data, actor))


@router.patch("/{admin_id}", response_model=AdminOut)
def update_admin(admin_id: int, data: AdminUpdate, db: DbSession, actor: Actor) -> AdminOut:
    return AdminOut.model_validate(admin_service.update(db, admin_id, data, actor))


@router.post("/{admin_id}/activate", response_model=AdminOut)
def activate_admin(admin_id: int, db: DbSession, actor: Actor) -> AdminOut:
    return AdminOut.model_validate(admin_service.set_active(db, admin_id, True, actor))


@router.post("/{admin_id}/deactivate", response_model=AdminOut)
def deactivate_admin(admin_id: int, db: DbSession, actor: Actor) -> AdminOut:
    return AdminOut.model_validate(admin_service.set_active(db, admin_id, False, actor))
