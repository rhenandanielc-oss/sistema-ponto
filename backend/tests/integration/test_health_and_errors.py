from alembic import command
from fastapi.testclient import TestClient

from tests.conftest import alembic_config


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").json() == {"status": "ok", "database": "ok"}


def test_error_format_and_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/nao-existe")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["x-request-id"]


def test_validation_error_format(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "nao-e-email"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {tuple(f["loc"]) for f in error["details"]["fields"]} >= {
        ("body", "email"),
        ("body", "password"),
    }


def test_openapi_is_published(client: TestClient) -> None:
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/employees" in spec["paths"]


def test_migration_downgrade_and_upgrade_roundtrip() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
