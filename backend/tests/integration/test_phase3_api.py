"""Fase 3: auditoria, resumo do banco de horas, limitação de taxa, proteção HTTP e OpenAPI."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.conftest import login
from tests.integration.helpers import create_employee, full_day, local


def test_audit_logs_filters(client: TestClient, auth_headers, admin) -> None:
    employee = create_employee(client, auth_headers)
    client.patch(f"/api/v1/employees/{employee}", json={"name": "João Silva"}, headers=auth_headers)
    login(client, password="senha-errada-123")

    everything = client.get("/api/v1/audit-logs", headers=auth_headers).json()
    actions = [i["action"] for i in everything["items"]]
    assert actions[0] == "auth.login_failed"  # mais recente primeiro
    assert {"employee.create", "employee.update", "auth.login", "admin.create"} <= set(actions)

    of_employee = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "employee", "entity_id": employee, "sort": "occurred_at"},
        headers=auth_headers,
    ).json()
    assert [i["action"] for i in of_employee["items"]] == ["employee.create", "employee.update"]
    assert of_employee["items"][1]["before"]["name"] == "João"
    assert of_employee["items"][1]["actor_admin_id"] == admin.id

    by_prefix = client.get(
        "/api/v1/audit-logs", params={"action": "auth."}, headers=auth_headers
    ).json()
    assert {i["action"] for i in by_prefix["items"]} == {"auth.login", "auth.login_failed"}

    exact = client.get(
        "/api/v1/audit-logs", params={"action": "auth.login"}, headers=auth_headers
    ).json()
    assert {i["action"] for i in exact["items"]} == {"auth.login"}


def test_audit_logs_period_is_inclusive_in_company_timezone(
    client: TestClient, auth_headers
) -> None:
    clock.freeze(local(1, "23:30"))  # 02:30 UTC do dia 2
    create_employee(client, auth_headers)
    clock.freeze(None)
    day_1 = client.get(
        "/api/v1/audit-logs",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01", "action": "employee.create"},
        headers=auth_headers,
    ).json()
    # O registro é de 01/09 no fuso da empresa, apesar de ser 02/09 em UTC.
    assert day_1["total"] == 1
    assert day_1["items"][0]["occurred_at"].startswith("2026-09-01T23:30")


def test_hour_bank_summary(client: TestClient, auth_headers, db: Session) -> None:
    ana = create_employee(client, auth_headers, registration="A", name="Ana")
    bruno = create_employee(client, auth_headers, registration="B", name="Bruno")
    full_day(db, ana, 1, "08:00", "12:00", "13:00", "18:00")  # +60
    full_day(db, bruno, 1, "08:30", "12:00", "13:00", "17:00")  # -30
    client.post(f"/api/v1/employees/{bruno}/deactivate", headers=auth_headers)
    clock.freeze(local(1, "20:00"))

    summary = client.get(
        "/api/v1/hour-bank/summary",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01"},
        headers=auth_headers,
    ).json()
    assert summary["total"] == 2
    rows = {r["name"]: r for r in summary["items"]}
    assert rows["Ana"]["closing_balance_minutes"] == 60
    assert rows["Ana"]["overtime_minutes"] == 60
    assert rows["Bruno"]["closing_balance_minutes"] == -30
    assert rows["Bruno"]["missing_minutes"] == 30

    active_only = client.get(
        "/api/v1/hour-bank/summary",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01", "status": "ACTIVE"},
        headers=auth_headers,
    ).json()
    assert [r["name"] for r in active_only["items"]] == ["Ana"]


def test_login_rate_limit(client: TestClient, admin) -> None:
    for _ in range(20):
        assert login(client, email="ninguem@empresa.com").status_code == 401
    blocked = login(client)  # mesmo com a senha certa, o IP está limitado
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked.headers["retry-after"]) > 0


def test_kiosk_rate_limit_counts_invalid_tokens(client: TestClient) -> None:
    for _ in range(120):
        assert (
            client.get("/api/v1/kiosk/ping", headers={"Authorization": "Device x"}).status_code
            == 403
        )
    assert client.get("/api/v1/kiosk/ping").status_code == 429


def test_security_headers(client: TestClient, auth_headers) -> None:
    response = client.get("/api/v1/employees", headers=auth_headers)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_body_too_large(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/holidays",
        content=b"{" + b" " * (1024 * 1024 + 10) + b"}",
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_openapi_documents_every_operation(client: TestClient) -> None:
    spec = client.get("/api/v1/openapi.json").json()
    declared_tags = {t["name"] for t in spec["tags"]}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("tags"), f"{method} {path} sem tag"
            assert set(operation["tags"]) <= declared_tags, f"{method} {path}: tag não declarada"
    assert "/api/v1/hour-bank/summary" in spec["paths"]
    assert "/api/v1/audit-logs" in spec["paths"]
