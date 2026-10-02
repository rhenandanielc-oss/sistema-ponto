from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict, not_found
from app.core.security import hash_password
from app.models import Admin
from app.schemas.admin import AdminCreate, AdminUpdate
from app.services import audit
from app.services.auth_service import revoke_all_for_admin


def _email_taken() -> AppError:
    return conflict("CONFLICT", "Já existe um administrador com este e-mail.")


def _snapshot(admin: Admin) -> dict[str, object]:
    return {"email": admin.email, "name": admin.name, "is_active": admin.is_active}


def get(db: Session, admin_id: int) -> Admin:
    admin = db.get(Admin, admin_id)
    if admin is None:
        raise not_found("Administrador não encontrado.")
    return admin


def list_admins(db: Session, page: int, page_size: int) -> tuple[list[Admin], int]:
    total = db.scalar(select(func.count()).select_from(Admin)) or 0
    items = db.scalars(
        select(Admin).order_by(Admin.name, Admin.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(items), total


def create(db: Session, data: AdminCreate, actor: audit.Actor) -> Admin:
    if db.scalar(select(Admin.id).where(func.lower(Admin.email) == data.email.lower())):
        raise _email_taken()
    admin = Admin(
        email=data.email.lower(), name=data.name, password_hash=hash_password(data.password)
    )
    db.add(admin)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _email_taken() from exc
    audit.record(
        db,
        actor=actor,
        action="admin.create",
        entity_type="admin",
        entity_id=admin.id,
        after=_snapshot(admin),
    )
    db.commit()
    return admin


def update(db: Session, admin_id: int, data: AdminUpdate, actor: audit.Actor) -> Admin:
    admin = get(db, admin_id)
    before = _snapshot(admin)
    if data.name is not None:
        admin.name = data.name
    if data.password is not None:
        admin.password_hash = hash_password(data.password)
        revoke_all_for_admin(db, admin.id)
    audit.record(
        db,
        actor=actor,
        action="admin.update",
        entity_type="admin",
        entity_id=admin.id,
        before=before,
        after={**_snapshot(admin), "password_changed": data.password is not None},
    )
    db.commit()
    return admin


def set_active(db: Session, admin_id: int, active: bool, actor: audit.Actor) -> Admin:
    # Bloqueia todos os administradores para que duas desativações simultâneas
    # não deixem o sistema sem nenhum administrador ativo.
    db.scalars(select(Admin.id).order_by(Admin.id).with_for_update()).all()
    admin = get(db, admin_id)
    if admin.is_active == active:
        return admin
    if not active:
        if actor.admin_id == admin.id:
            raise conflict("CONFLICT", "Você não pode desativar a si mesmo.")
        active_count = db.scalar(select(func.count()).where(Admin.is_active.is_(True))) or 0
        if active_count <= 1:
            raise conflict("CONFLICT", "Não é possível desativar o último administrador ativo.")
        revoke_all_for_admin(db, admin.id)
    before = _snapshot(admin)
    admin.is_active = active
    audit.record(
        db,
        actor=actor,
        action="admin.activate" if active else "admin.deactivate",
        entity_type="admin",
        entity_id=admin.id,
        before=before,
        after=_snapshot(admin),
    )
    db.commit()
    return admin
