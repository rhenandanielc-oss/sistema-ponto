"""Início do controle de ponto e "zerar banco de horas" (BUSINESS-RULES.md §9.2 e §9.3)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local


def bank(client: TestClient, headers, employee: int, date_from: str, date_to: str):
    response = client.get(
        f"/api/v1/employees/{employee}/hour-bank",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_days_before_tracking_start_are_not_absences(
    client: TestClient, auth_headers, db: Session
) -> None:
    # Admitido em 01/09, mas o restaurante começou a usar o sistema em 06/10.
    employee = create_employee(client, auth_headers, hire_date="2026-09-01", payday=1)
    clock.freeze(local(6, "18:00", month=10))
    before = bank(client, auth_headers, employee, "2026-10-01", "2026-10-05")
    assert before["totals"]["absences"] > 0  # sem a configuração: faltas desde a admissão

    response = client.patch(
        "/api/v1/settings", json={"tracking_start_date": "2026-10-06"}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["tracking_start_date"] == "2026-10-06"

    after = bank(client, auth_headers, employee, "2026-09-01", "2026-10-05")
    assert after["totals"]["absences"] == 0
    assert after["totals"]["planned_minutes"] == 0
    assert after["closing_balance_minutes"] == 0
    assert {d["day_type"] for d in after["days"]} == {"BEFORE_TRACKING"}

    # Ciclo com pagamento dia 1: 02/10 a 01/11; só conta a partir de 06/10.
    payroll = client.get(f"/api/v1/employees/{employee}/payroll", headers=auth_headers).json()
    assert payroll["period_start"] == "2026-10-02"
    assert payroll["missing_minutes"] == 480  # só 06/10 (já terminou sem batida), não 02–05/10


def test_reset_hour_bank_zeroes_the_balance(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers, hire_date="2026-09-01")
    full_day(db, employee, 1, "08:00", "17:00")  # terça 01/09 ok; o resto da semana: faltas
    clock.freeze(local(4, "20:00"))
    assert (
        bank(client, auth_headers, employee, "2026-09-01", "2026-09-04")["closing_balance_minutes"]
        < 0
    )

    url = f"/api/v1/employees/{employee}/hour-bank/reset"
    reset = client.post(url, json={}, headers=auth_headers)
    assert reset.status_code == 201, reset.text
    assert reset.json()["kind"] == "CORRECTION" and reset.json()["entry_date"] == "2026-09-04"
    assert (
        bank(client, auth_headers, employee, "2026-09-01", "2026-09-04")["closing_balance_minutes"]
        == 0
    )
    assert client.post(url, json={}, headers=auth_headers).status_code == 409  # já zerado

    # Os dias seguintes voltam a contar a partir do zero.
    clock.freeze(local(8, "20:00"))
    assert (
        bank(client, auth_headers, employee, "2026-09-07", "2026-09-07")["closing_balance_minutes"]
        < 0
    )
