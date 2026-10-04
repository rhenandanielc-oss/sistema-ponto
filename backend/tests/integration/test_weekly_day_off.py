"""Folga semanal em qualquer dia pela API (BUSINESS-RULES.md §3.2)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local

EVERY_DAY = {
    "weekdays": ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"],
    "start_time": "08:00",
    "end_time": "16:00",
    "lunch_minutes": 0,
    "weekly_day_off": True,
}


def work(db: Session, employee: int, days: list[int]) -> None:
    for day in days:
        full_day(db, employee, day, "08:00", "16:00")


def bank(client: TestClient, headers, employee: int, date_from: str, date_to: str):
    response = client.get(
        f"/api/v1/employees/{employee}/hour-bank",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_day_off_on_thursday_then_on_sunday(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers, hire_date="2026-09-07", schedule=EVERY_DAY)
    detail = client.get(f"/api/v1/employees/{employee}", headers=auth_headers).json()
    assert detail["current_schedule"]["weekly_day_off"] is True

    # Semana 07–13/09: folga na quinta (10). Semana 14–20/09: folga no domingo (20).
    work(db, employee, [7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19])
    clock.freeze(local(21, "10:00"))

    result = bank(client, auth_headers, employee, "2026-09-07", "2026-09-20")
    totals = result["totals"]
    assert (totals["absences"], totals["missing_minutes"], totals["overtime_minutes"]) == (0, 0, 0)
    assert totals["planned_minutes"] == 12 * 480
    assert result["closing_balance_minutes"] == 0
    day_offs = [d["date"] for d in result["days"] if "WEEKLY_DAY_OFF" in d["flags"]]
    assert day_offs == ["2026-09-10", "2026-09-20"]

    # Período começando no meio da semana: a folga de quinta continua valendo.
    partial = bank(client, auth_headers, employee, "2026-09-11", "2026-09-13")
    assert [d["status"] for d in partial["days"]] == ["OK", "OK", "OK"]
    assert partial["opening_balance_minutes"] == 0


def test_second_day_without_punches_is_an_absence_and_full_week_is_overtime(
    client: TestClient, auth_headers, db: Session
) -> None:
    employee = create_employee(client, auth_headers, hire_date="2026-09-07", schedule=EVERY_DAY)
    work(db, employee, [7, 8, 9, 10, 11, 12, 13])  # semana inteira: domingo vira extra
    work(db, employee, [14, 16, 17, 18, 19])  # faltou terça (folga) e domingo (falta)
    clock.freeze(local(21, "10:00"))

    days = {
        d["date"]: d
        for d in bank(client, auth_headers, employee, "2026-09-07", "2026-09-20")["days"]
    }
    sunday_worked = days["2026-09-13"]
    assert (sunday_worked["planned_minutes"], sunday_worked["overtime_minutes"]) == (0, 480)
    assert "DAY_OFF_WORK" in sunday_worked["flags"]
    assert "WEEKLY_DAY_OFF" in days["2026-09-15"]["flags"]
    assert days["2026-09-20"]["status"] == "ABSENT"
