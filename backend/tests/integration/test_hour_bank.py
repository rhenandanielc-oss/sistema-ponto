"""Cálculo por período e banco de horas via API (TEST-PLAN.md C15, C16, C18–C22)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local, punch


def get_bank(client: TestClient, headers, employee: int, date_from: str, date_to: str) -> dict:
    response = client.get(
        f"/api/v1/employees/{employee}/hour-bank",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_c19_c20_period_is_inclusive(client: TestClient, auth_headers) -> None:
    employee = create_employee(client, auth_headers)
    clock.freeze(local(1, "12:00", month=10))
    month = client.get(
        f"/api/v1/employees/{employee}/workdays",
        params={"date_from": "2026-09-01", "date_to": "2026-09-30"},
        headers=auth_headers,
    ).json()
    assert len(month["days"]) == 30
    assert (month["days"][0]["date"], month["days"][-1]["date"]) == ("2026-09-01", "2026-09-30")

    one_day = client.get(
        f"/api/v1/employees/{employee}/workdays",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01"},
        headers=auth_headers,
    ).json()
    assert len(one_day["days"]) == 1


def test_period_validation(client: TestClient, auth_headers) -> None:
    employee = create_employee(client, auth_headers)
    url = f"/api/v1/employees/{employee}/workdays"
    inverted = client.get(
        url, params={"date_from": "2026-09-30", "date_to": "2026-09-01"}, headers=auth_headers
    )
    assert inverted.status_code == 422
    too_long = client.get(
        url, params={"date_from": "2025-01-01", "date_to": "2026-09-01"}, headers=auth_headers
    )
    assert too_long.status_code == 422


def test_c21_hour_bank(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    full_day(db, employee, 1, "08:20", "12:00", "13:00", "17:00")  # C04: -20
    full_day(db, employee, 2, "08:00", "12:00", "13:00", "18:30")  # C08: +90
    punch(db, employee, "ENTRY", local(3, "08:00"))  # C10: incompleto, fora do banco
    punch(db, employee, "LUNCH_EXIT", local(3, "12:00"))
    clock.freeze(local(4, "07:00"))

    for minutes, kind, reason in [
        (120, "OPENING_BALANCE", "Saldo do controle anterior"),
        (-60, "COMPENSATION", "Folga compensatória concedida"),
    ]:
        response = client.post(
            f"/api/v1/employees/{employee}/hour-bank/entries",
            json={"entry_date": "2026-09-01", "minutes": minutes, "kind": kind, "reason": reason},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text

    bank = get_bank(client, auth_headers, employee, "2026-09-01", "2026-09-03")
    assert bank["opening_balance_minutes"] == 0
    assert bank["entries_minutes"] == 60
    assert bank["totals"]["balance_minutes"] == 70
    assert bank["totals"]["incomplete_days"] == 1
    assert bank["closing_balance_minutes"] == 120 - 20 + 90 - 60  # +130
    statuses = [d["status"] for d in bank["days"]]
    assert statuses == ["OK", "OK", "INCOMPLETE"]


def test_c22_opening_balance_counts_days_before_period(
    client: TestClient, auth_headers, db: Session
) -> None:
    employee = create_employee(client, auth_headers)
    full_day(db, employee, 1, "08:00", "12:00", "13:00", "18:00")  # +60 (antes do período)
    full_day(db, employee, 2, "08:00", "12:00", "13:00", "17:30")  # +30 (no período)
    clock.freeze(local(2, "20:00"))

    bank = get_bank(client, auth_headers, employee, "2026-09-02", "2026-09-02")
    assert bank["opening_balance_minutes"] == 60
    assert bank["closing_balance_minutes"] == 90


def test_absence_holiday_and_weekend(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    client.post(
        "/api/v1/holidays",
        json={"date": "2025-09-07", "name": "Independência", "recurring": True},
        headers=auth_headers,
    )
    full_day(db, employee, 5, "08:00", "12:00")  # sábado trabalhado: +240
    clock.freeze(local(9, "07:00"))

    bank = get_bank(client, auth_headers, employee, "2026-09-04", "2026-09-08")
    by_date = {d["date"]: d for d in bank["days"]}
    assert by_date["2026-09-04"]["status"] == "ABSENT"  # sexta sem batidas: -480
    assert "DAY_OFF_WORK" in by_date["2026-09-05"]["flags"]
    assert by_date["2026-09-06"]["status"] == "NONE"  # domingo
    assert (by_date["2026-09-07"]["day_type"], by_date["2026-09-07"]["balance_minutes"]) == (
        "HOLIDAY",
        0,
    )
    assert by_date["2026-09-08"]["status"] == "ABSENT"
    assert bank["totals"]["absences"] == 2
    # 01 a 03/09 (antes do período) também são faltas: entram no saldo anterior.
    assert bank["opening_balance_minutes"] == -3 * 480
    assert bank["closing_balance_minutes"] == -3 * 480 + (-480 + 240 - 480)


def test_c18_schedule_change_applies_from_valid_from(
    client: TestClient, auth_headers, db: Session
) -> None:
    employee = create_employee(client, auth_headers)
    response = client.post(
        f"/api/v1/employees/{employee}/schedules",
        json={"valid_from": "2026-09-16", "start_time": "09:00", "end_time": "16:00"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    full_day(db, employee, 16, "09:20", "12:00", "13:00", "16:00")
    clock.freeze(local(17, "07:00"))

    days = client.get(
        f"/api/v1/employees/{employee}/workdays",
        params={"date_from": "2026-09-15", "date_to": "2026-09-16"},
        headers=auth_headers,
    ).json()["days"]
    assert days[0]["planned_minutes"] == 480
    assert (days[1]["planned_minutes"], days[1]["late_minutes"], days[1]["balance_minutes"]) == (
        360,
        20,
        -20,
    )


def test_hour_bank_entry_validation(client: TestClient, auth_headers) -> None:
    employee = create_employee(client, auth_headers)
    url = f"/api/v1/employees/{employee}/hour-bank/entries"
    zero = client.post(
        url,
        json={
            "entry_date": "2026-09-01",
            "minutes": 0,
            "kind": "CORRECTION",
            "reason": "Ajuste de saldo",
        },
        headers=auth_headers,
    )
    assert zero.status_code == 422
    unknown = client.post(
        "/api/v1/employees/999/hour-bank/entries",
        json={
            "entry_date": "2026-09-01",
            "minutes": 10,
            "kind": "CORRECTION",
            "reason": "Ajuste de saldo",
        },
        headers=auth_headers,
    )
    assert unknown.status_code == 404
    assert client.get(url, headers=auth_headers).json() == []


def test_extra_day_outside_registered_days_is_overtime(
    client: TestClient, auth_headers, db: Session
) -> None:
    """Funcionário de segunda a sexta que trabalha no sábado: tudo vira hora extra."""
    employee = create_employee(
        client,
        auth_headers,
        schedule={
            "weekdays": ["segunda", "terça", "quarta", "quinta", "sexta"],
            "start_time": "08:00",
            "end_time": "16:00",
            "lunch_minutes": 60,
        },
    )
    full_day(db, employee, 5, "08:00", "12:00", "12:30", "14:00")  # sábado 05/09
    clock.freeze(local(6, "08:00"))
    day = get_bank(client, auth_headers, employee, "2026-09-05", "2026-09-05")["days"][0]
    assert (day["day_type"], day["planned_minutes"]) == ("DAY_OFF", 0)
    assert (day["worked_minutes"], day["overtime_minutes"], day["balance_minutes"]) == (
        330,
        330,
        330,
    )
    assert "DAY_OFF_WORK" in day["flags"]
