from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import TokenExpired, TokenInvalid, decode_access_token
from app.db.session import get_db
from app.models import Admin
from app.services import audit

DbSession = Annotated[Session, Depends(get_db)]

_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_current_admin(
    db: DbSession, authorization: Annotated[str | None, Header()] = None
) -> Admin:
    """Exige um administrador autenticado e ativo. Usado em todas as rotas administrativas."""
    if not authorization:
        raise AppError(
            401, "UNAUTHENTICATED", "Autenticação necessária.", headers=_BEARER_CHALLENGE
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError(
            401, "UNAUTHENTICATED", "Autenticação necessária.", headers=_BEARER_CHALLENGE
        )
    try:
        admin_id = decode_access_token(token)
    except TokenExpired as exc:
        raise AppError(401, "TOKEN_EXPIRED", "Sessão expirada.", headers=_BEARER_CHALLENGE) from exc
    except TokenInvalid as exc:
        raise AppError(
            401, "UNAUTHENTICATED", "Autenticação necessária.", headers=_BEARER_CHALLENGE
        ) from exc
    admin = db.get(Admin, admin_id)
    if admin is None or not admin.is_active:
        raise AppError(
            401, "UNAUTHENTICATED", "Autenticação necessária.", headers=_BEARER_CHALLENGE
        )
    return admin


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def admin_actor(admin: CurrentAdmin) -> audit.Actor:
    return audit.admin_actor(admin.id)


Actor = Annotated[audit.Actor, Depends(admin_actor)]


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> None:
        self.page = page
        self.page_size = page_size


PageParams = Annotated[Pagination, Depends()]
