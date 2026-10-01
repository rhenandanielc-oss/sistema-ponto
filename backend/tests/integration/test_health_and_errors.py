import base64
import json

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.main import create_app
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


def test_access_log_is_json_with_request_id_and_without_secrets(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("json", "INFO")
    try:
        response = client.post(
            "/api/v1/auth/login?origem=teste",
            json={"email": "x@empresa.com", "password": "senha-que-nao-pode-vazar"},
        )
    finally:
        configure_logging("text", "INFO")
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    access = [line for line in lines if line["logger"] == "app.access"]
    assert access[-1]["path"] == "/api/v1/auth/login"  # sem a query string
    assert access[-1]["status"] == response.status_code == 401
    assert access[-1]["request_id"] == response.headers["x-request-id"]
    assert "senha-que-nao-pode-vazar" not in json.dumps(lines)


def test_production_hides_interactive_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("BIOMETRIC_KEY", base64.b64encode(b"k" * 32).decode())
    monkeypatch.setenv("FACE_ENGINE", "opencv")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as prod:
            assert prod.get("/api/docs").status_code == 404
            assert prod.get("/api/v1/openapi.json").status_code == 404
            assert prod.get("/api/v1/health/live").status_code == 200
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
