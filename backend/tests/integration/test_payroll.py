"""Horas do ciclo de pagamento (BUSINESS-RULES.md §11)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local, punch


def test_hours_of_payment_cycle(client: TestClient, auth_headers, db: Session) -> None:
    # Pagamento dia 5: o pagamento de setembro cobre 06/08 a 05/09 (admissão em 01/09).
    employee = create_employee(client, auth_headers, payday=5)
    full_day(db, employee, 1, "08:00", "12:00", "13:00", "17:00")  # 8h00
    full_day(db, employee, 2, "08:00", "12:00", "13:00", "18:30")  # 9h30 (+1h30)
    # 03/09: falta
    full_day(db, employee, 4, "08:30", "12:00", "13:00", "17:00")  # 7h30 (-0h30)
    clock.freeze(local(10, "12:00"))

    response = client.get(
        f"/api/v1/employees/{employee}/payroll",
        params={"payment_month": "2026-09"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    p = response.json()
    assert (p["period_start"], p["period_end"], p["payment_date"]) == (
        "2026-08-06",
        "2026-09-05",
        "2026-09-05",
    )
    assert p["closed"] is True
    assert (p["worked_minutes"], p["worked_hours"]) == (1500, 25.0)  # 8 + 9,5 + 7,5
    assert (p["planned_minutes"], p["planned_hours"]) == (4 * 480, 32.0)
    assert p["overtime_hours"] == 1.5
    assert p["missing_hours"] == 8.5  # falta (8 h) + atraso (0,5 h)
    assert p["absences"] == 1
    assert p["incomplete_days"] == 0
    # Horas fixas (32 h) + extras (1,5 h) − faltantes (8,5 h) = 25 h a pagar.
    assert (p["payable_minutes"], p["payable_hours"]) == (1500, 25.0)


def test_payable_hours_respect_tolerance(client: TestClient, auth_headers, db: Session) -> None:
    """Variação dentro da tolerância não desconta: paga as horas fixas cheias."""
    employee = create_employee(client, auth_headers, payday=5)
    full_day(db, employee, 1, "08:04", "12:00", "13:00", "17:03")  # 7h59 trabalhadas
    full_day(db, employee, 2, "08:00", "12:00", "13:00", "17:00")
    full_day(db, employee, 3, "08:00", "12:00", "13:00", "17:00")
    full_day(db, employee, 4, "08:00", "12:00", "13:00", "19:00")  # +2 h
    clock.freeze(local(10, "12:00"))
    p = client.get(
        f"/api/v1/employees/{employee}/payroll",
        params={"payment_month": "2026-09"},
        headers=auth_headers,
    ).json()
    assert p["worked_minutes"] == 479 + 480 + 480 + 600
    assert p["planned_hours"] == 32.0
    assert (p["overtime_hours"], p["missing_hours"]) == (2.0, 0.0)
    assert p["payable_hours"] == 34.0  # 32 + 2 − 0


def test_current_cycle_by_reference_date(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers, payday=5)
    punch(db, employee, "ENTRY", local(8, "08:00"))
    clock.freeze(local(8, "12:00"))
    current = client.get(f"/api/v1/employees/{employee}/payroll", headers=auth_headers).json()
    # Hoje (08/09) está no ciclo 06/09 a 05/10, ainda em andamento.
    assert (current["period_start"], current["period_end"], current["closed"]) == (
        "2026-09-06",
        "2026-10-05",
        False,
    )
    by_reference = client.get(
        f"/api/v1/employees/{employee}/payroll",
        params={"reference_date": "2026-09-05"},
        headers=auth_headers,
    ).json()
    assert by_reference["period_end"] == "2026-09-05"


def test_incomplete_days_are_reported(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers, payday=5)
    punch(db, employee, "ENTRY", local(1, "08:00"))  # esqueceu a saída
    clock.freeze(local(10, "12:00"))
    p = client.get(
        f"/api/v1/employees/{employee}/payroll",
        params={"payment_month": "2026-09"},
        headers=auth_headers,
    ).json()
    assert p["incomplete_days"] == 1


def test_payday_is_required_validated_and_editable(client: TestClient, auth_headers) -> None:
    base = {
        "name": "Ana",
        "registration_number": "X1",
        "hire_date": "2026-09-01",
        "schedule": {"start_time": "08:00", "end_time": "17:00"},
    }
    assert client.post("/api/v1/employees", json=base, headers=auth_headers).status_code == 422
    assert (
        client.post(
            "/api/v1/employees", json={**base, "payday": 32}, headers=auth_headers
        ).status_code
        == 422
    )
    created = client.post("/api/v1/employees", json={**base, "payday": 31}, headers=auth_headers)
    assert created.json()["payday"] == 31
    employee = created.json()["id"]

    updated = client.patch(
        f"/api/v1/employees/{employee}", json={"payday": 20}, headers=auth_headers
    )
    assert updated.json()["payday"] == 20
    history = client.get(f"/api/v1/employees/{employee}/history", headers=auth_headers).json()
    assert history["items"][0]["before"]["payday"] == 31
    assert history["items"][0]["after"]["payday"] == 20


def test_summary_uses_each_employee_payday(client: TestClient, auth_headers) -> None:
    create_employee(client, auth_headers, registration="A", name="Ana", payday=5)
    create_employee(client, auth_headers, registration="B", name="Bruno", payday=20)
    clock.freeze(local(10, "12:00"))
    summary = client.get(
        "/api/v1/payroll", params={"reference_date": "2026-09-10"}, headers=auth_headers
    ).json()
    periods = {r["name"]: (r["period_start"], r["period_end"]) for r in summary["items"]}
    assert periods == {
        "Ana": ("2026-09-06", "2026-10-05"),
        "Bruno": ("2026-08-21", "2026-09-20"),
    }
    by_month = client.get(
        "/api/v1/payroll", params={"payment_month": "2026-09"}, headers=auth_headers
    ).json()
    assert {r["name"]: r["payment_date"] for r in by_month["items"]} == {
        "Ana": "2026-09-05",
        "Bruno": "2026-09-20",
    }


def test_invalid_payment_month(client: TestClient, auth_headers) -> None:
    employee = create_employee(client, auth_headers)
    for month in ("2026-13", "2026-9", "setembro"):
        response = client.get(
            f"/api/v1/employees/{employee}/payroll",
            params={"payment_month": month},
            headers=auth_headers,
        )
        assert response.status_code == 422, month
