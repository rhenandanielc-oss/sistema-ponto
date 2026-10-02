"""Autenticação do administrador (TEST-PLAN.md §5, casos A01–A09)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.models import AuditLog
from tests.conftest import ADMIN_PASSWORD, login

ME = "/api/v1/auth/me"
REFRESH = "/api/v1/auth/refresh"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def actions(db: Session) -> list[str]:
    db.expire_all()
    return list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)).all())


def test_a01_login_returns_token_and_httponly_refresh_cookie(client: TestClient, admin, db) -> None:
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["admin"]["email"] == "admin@empresa.com"
    assert "password_hash" not in body["admin"]

    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert response.headers["cache-control"] == "no-store"

    me = client.get(ME, headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == admin.id
    assert "auth.login" in actions(db)


def test_login_email_is_case_insensitive(client: TestClient, admin) -> None:
    assert login(client, email="ADMIN@Empresa.com").status_code == 200


def test_a02_wrong_password_and_unknown_email_get_same_answer(
    client: TestClient, admin, db
) -> None:
    wrong_password = login(client, password="senha-errada-123")
    unknown_email = login(client, email="ninguem@empresa.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]
    assert wrong_password.json()["error"]["code"] == "UNAUTHENTICATED"
    assert actions(db).count("auth.login_failed") == 2


def test_a03_five_failures_lock_the_account_for_15_minutes(client: TestClient, admin, db) -> None:
    start = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    clock.freeze(start)
    for _ in range(5):
        assert login(client, password="senha-errada-123").status_code == 401

    locked = login(client)  # senha correta, mas conta bloqueada
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert "auth.account_locked" in actions(db)

    clock.freeze(start + timedelta(minutes=14))
    assert login(client).status_code == 423

    clock.freeze(start + timedelta(minutes=16))
    assert login(client).status_code == 200


def test_successful_login_resets_failure_counter(client: TestClient, admin) -> None:
    for _ in range(4):
        login(client, password="senha-errada-123")
    assert login(client).status_code == 200
    for _ in range(4):
        login(client, password="senha-errada-123")
    assert login(client).status_code == 200


def test_a04_expired_access_token(client: TestClient, admin) -> None:
    clock.freeze(datetime.now(UTC) - timedelta(minutes=16))
    token = login(client).json()["access_token"]
    clock.freeze(None)
    response = client.get(ME, headers=bearer(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_tampered_token_is_rejected(client: TestClient, admin) -> None:
    token = login(client).json()["access_token"]
    response = client.get(ME, headers=bearer(token[:-2] + "xx"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a05_refresh_rotates_and_reuse_revokes_family(client: TestClient, admin, db) -> None:
    first_cookie = login(client).cookies["refresh_token"]

    rotated = client.post(REFRESH)
    assert rotated.status_code == 200
    second_cookie = rotated.cookies["refresh_token"]
    assert second_cookie != first_cookie
    assert client.get(ME, headers=bearer(rotated.json()["access_token"])).status_code == 200

    # Reuso do primeiro token (já rotacionado): indício de roubo.
    client.cookies.set("refresh_token", first_cookie, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401
    assert "auth.refresh_reuse_detected" in actions(db)

    # O token legítimo mais recente também foi revogado.
    client.cookies.set("refresh_token", second_cookie, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401


def test_refresh_without_cookie(client: TestClient) -> None:
    assert client.post(REFRESH).status_code == 401


def test_refresh_token_expires(client: TestClient, admin) -> None:
    start = datetime.now(UTC)
    clock.freeze(start)
    login(client)
    clock.freeze(start + timedelta(hours=8, minutes=1))
    assert client.post(REFRESH).status_code == 401


def test_a06_logout_revokes_refresh_token(client: TestClient, admin, db) -> None:
    cookie = login(client).cookies["refresh_token"]
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    client.cookies.set("refresh_token", cookie, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401
    assert "auth.logout" in actions(db)


def test_a07_deactivated_admin_cannot_login_refresh_or_use_token(client: TestClient, db) -> None:
    from tests.conftest import make_admin

    make_admin(db, "chefe@empresa.com", "Chefe")
    other = make_admin(db, "outro@empresa.com", "Outro")
    chief_headers = bearer(login(client, "chefe@empresa.com").json()["access_token"])

    other_client = TestClient(client.app)
    other_token = login(other_client, "outro@empresa.com").json()["access_token"]

    response = client.post(f"/api/v1/admins/{other.id}/deactivate", headers=chief_headers)
    assert response.status_code == 200

    assert login(other_client, "outro@empresa.com").status_code == 401
    assert other_client.post(REFRESH).status_code == 401
    assert other_client.get(ME, headers=bearer(other_token)).status_code == 401


def test_a09_device_token_is_not_accepted_on_admin_routes(client: TestClient, admin) -> None:
    response = client.get("/api/v1/employees", headers={"Authorization": "Device abc123"})
    assert response.status_code == 401


def test_password_is_never_stored_in_plain_text(db: Session, admin) -> None:
    assert ADMIN_PASSWORD not in admin.password_hash
    assert admin.password_hash.startswith("$argon2id$")
