"""Login, refresh e logout do administrador (SECURITY.md §3)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.request_context import current_request
from app.core.security import (
    create_access_token,
    new_opaque_token,
    refresh_expiry,
    sha256_hex,
    verify_password,
)
from app.models import Admin, RefreshToken
from app.services import audit


def _invalid_credentials() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "Credenciais inválidas.")


def _invalid_refresh() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "Sessão inválida ou expirada.")


@dataclass(frozen=True)
class AuthSession:
    admin: Admin
    access_token: str
    expires_in: int
    refresh_token: str


def _issue(db: Session, admin: Admin, family_id: uuid.UUID) -> AuthSession:
    raw = new_opaque_token()
    req = current_request()
    db.add(
        RefreshToken(
            admin_id=admin.id,
            token_hash=sha256_hex(raw),
            family_id=family_id,
            expires_at=refresh_expiry(),
            user_agent=req.user_agent if req else None,
            ip=req.ip if req else None,
        )
    )
    access, expires_in = create_access_token(admin.id)
    return AuthSession(admin=admin, access_token=access, expires_in=expires_in, refresh_token=raw)


def login(db: Session, email: str, password: str) -> AuthSession:
    settings = get_settings()
    now = now_utc()
    admin = db.scalar(
        select(Admin).where(func.lower(Admin.email) == email.lower()).with_for_update()
    )

    if admin is None:
        verify_password(password, None)  # mesmo custo de tempo de um e-mail existente
        audit.record(
            db,
            actor=audit.ANONYMOUS,
            action="auth.login_failed",
            after={"email": email.lower(), "reason": "unknown_email"},
        )
        db.commit()
        raise _invalid_credentials()

    if admin.locked_until and admin.locked_until > now:
        audit.record(
            db,
            actor=audit.ANONYMOUS,
            action="auth.login_blocked",
            entity_type="admin",
            entity_id=admin.id,
        )
        db.commit()
        raise AppError(
            423,
            "ACCOUNT_LOCKED",
            "Conta bloqueada temporariamente. Tente novamente mais tarde.",
            {"locked_until": admin.locked_until.isoformat()},
        )

    if not verify_password(password, admin.password_hash) or not admin.is_active:
        reason = "inactive" if admin.is_active is False else "wrong_password"
        admin.failed_login_count += 1
        if admin.failed_login_count >= settings.login_max_failures:
            admin.failed_login_count = 0
            admin.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            audit.record(
                db,
                actor=audit.SYSTEM,
                action="auth.account_locked",
                entity_type="admin",
                entity_id=admin.id,
            )
        audit.record(
            db,
            actor=audit.ANONYMOUS,
            action="auth.login_failed",
            entity_type="admin",
            entity_id=admin.id,
            after={"reason": reason},
        )
        db.commit()
        raise _invalid_credentials()

    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now
    session = _issue(db, admin, uuid.uuid4())
    audit.record(
        db,
        actor=audit.admin_actor(admin.id),
        action="auth.login",
        entity_type="admin",
        entity_id=admin.id,
    )
    db.commit()
    return session


def refresh(db: Session, raw_token: str | None) -> AuthSession:
    if not raw_token:
        raise _invalid_refresh()
    now = now_utc()
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == sha256_hex(raw_token))
        .with_for_update()
    )
    if token is None:
        raise _invalid_refresh()

    if token.revoked_at is not None:
        # Token já rotacionado sendo reutilizado: indício de roubo. Revoga a família inteira.
        revoke_family(db, token.family_id, now)
        audit.record(
            db,
            actor=audit.SYSTEM,
            action="auth.refresh_reuse_detected",
            entity_type="admin",
            entity_id=token.admin_id,
        )
        db.commit()
        raise _invalid_refresh()

    admin = db.get(Admin, token.admin_id)
    if token.expires_at <= now or admin is None or not admin.is_active:
        token.revoked_at = now
        db.commit()
        raise _invalid_refresh()

    token.revoked_at = now
    session = _issue(db, admin, token.family_id)
    db.commit()
    return session


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw_token)))
    if token is None:
        return
    if token.revoked_at is None:
        token.revoked_at = now_utc()
    audit.record(
        db,
        actor=audit.admin_actor(token.admin_id),
        action="auth.logout",
        entity_type="admin",
        entity_id=token.admin_id,
    )
    db.commit()


def revoke_family(db: Session, family_id: uuid.UUID, when: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )


def revoke_all_for_admin(db: Session, admin_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.admin_id == admin_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
