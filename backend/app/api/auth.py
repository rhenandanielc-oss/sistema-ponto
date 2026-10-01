from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import get_settings
from app.schemas.auth import AdminOut, LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["autenticação"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _token_response(response: Response, session: auth_service.AuthSession) -> TokenResponse:
    _set_refresh_cookie(response, session.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        admin=AdminOut.model_validate(session.admin),
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    return _token_response(response, auth_service.login(db, data.email, data.password))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    return _token_response(response, auth_service.refresh(db, refresh_token))


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    auth_service.logout(db, refresh_token)
    response.status_code = 204
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response


@router.get("/me", response_model=AdminOut)
def me(admin: CurrentAdmin) -> AdminOut:
    return AdminOut.model_validate(admin)
