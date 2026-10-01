"""Ajustes do administrador e histórico (TEST-PLAN.md R16, R17; MASTER-PROMPT §14)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local, punch

RECORDS = "/api/v1/time-records"
ADJUST = "/api/v1/time-records/adjustments"


def test_add_forgotten_exit(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    punch(db, employee, "ENTRY", local(1, "08:00"))
    clock.freeze(local(2, "09:00"))

    response = client.post(
        ADJUST,
        json={
            "kind": "ADD",
            "employee_id": employee,
            "type": "EXIT",
            "recorded_at": local(1, "17:00").isoformat(),
            "reason": "Esqueceu de bater a saída",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    adjustment = response.json()

    record = client.get(f"{RECORDS}/{adjustment['record_id']}", headers=auth_headers).json()
    assert record["source"] == "ADJUSTMENT"
    assert record["workday_date"] == "2026-09-01"
    assert record["employee_name"] == "João"
    assert record["adjustments"][0]["reason"] == "Esqueceu de bater a saída"

    day = client.get(
        f"/api/v1/employees/{employee}/workdays",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01"},
        headers=auth_headers,
    ).json()["days"][0]
    assert (day["status"], day["worked_minutes"]) == ("OK", 540)


def test_r16_adjustment_validations(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    full_day(db, employee, 1, "08:00", "17:00")
    clock.freeze(local(2, "09:00"))
    base = {"kind": "ADD", "employee_id": employee, "reason": "Batida esquecida no dia"}

    short_reason = client.post(
        ADJUST,
        json={
            **base,
            "type": "LUNCH_EXIT",
            "recorded_at": local(1, "12:00").isoformat(),
            "reason": "curto",
        },
        headers=auth_headers,
    )
    assert short_reason.status_code == 422

    duplicate = client.post(
        ADJUST,
        json={**base, "type": "EXIT", "recorded_at": local(1, "18:00").isoformat()},
        headers=auth_headers,
    )
    assert duplicate.json()["error"]["code"] == "DUPLICATE_RECORD"

    out_of_order = client.post(
        ADJUST,
        json={**base, "type": "LUNCH_EXIT", "recorded_at": local(1, "07:00").isoformat()},
        headers=auth_headers,
    )
    assert out_of_order.json()["error"]["code"] == "INVALID_SEQUENCE"

    future = client.post(
        ADJUST,
        json={**base, "type": "LUNCH_EXIT", "recorded_at": local(3, "12:00").isoformat()},
        headers=auth_headers,
    )
    assert future.status_code == 422

    # Horário sem fuso (como o administrador digita) é interpretado no fuso da empresa.
    lunch = client.post(
        ADJUST,
        json={**base, "type": "LUNCH_EXIT", "recorded_at": "2026-09-01T12:00"},
        headers=auth_headers,
    )
    assert lunch.status_code == 201
    record = client.get(f"{RECORDS}/{lunch.json()['record_id']}", headers=auth_headers).json()
    assert record["recorded_at"] == "2026-09-01T12:00:00-03:00"


def test_r17_void_keeps_record_in_history(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    wrong = punch(db, employee, "ENTRY", local(1, "08:00"))
    clock.freeze(local(1, "08:30"))

    response = client.post(
        ADJUST,
        json={"kind": "VOID", "record_id": wrong.id, "reason": "Batida feita por engano"},
        headers=auth_headers,
    )
    assert response.status_code == 201

    visible = client.get(RECORDS, params={"employee_id": employee}, headers=auth_headers).json()
    assert visible["total"] == 0
    with_voided = client.get(
        RECORDS, params={"employee_id": employee, "include_voided": True}, headers=auth_headers
    ).json()
    assert with_voided["items"][0]["voided_at"] is not None

    again = client.post(
        ADJUST,
        json={"kind": "VOID", "record_id": wrong.id, "reason": "Batida feita por engano"},
        headers=auth_headers,
    )
    assert again.status_code == 409

    # Com a anulação, o funcionário pode bater a entrada de novo.
    punch(db, employee, "ENTRY", local(1, "08:40"))

    adjustments = client.get(ADJUST, params={"employee_id": employee}, headers=auth_headers).json()
    assert [a["kind"] for a in adjustments["items"]] == ["VOID"]


def test_history_filters_pagination_and_sort(client: TestClient, auth_headers, db: Session) -> None:
    joao = create_employee(client, auth_headers)
    maria = create_employee(client, auth_headers, registration="002", name="Maria")
    full_day(db, joao, 1, "08:00", "12:00", "13:00", "17:00")
    full_day(db, maria, 2, "08:00", "17:00")
    full_day(db, joao, 3, "08:00", "17:00")

    all_records = client.get(RECORDS, headers=auth_headers).json()
    assert all_records["total"] == 8
    assert all_records["items"][0]["recorded_at"].startswith("2026-09-03T17:00")

    only_joao = client.get(RECORDS, params={"employee_id": joao}, headers=auth_headers).json()
    assert only_joao["total"] == 6

    period = client.get(
        RECORDS, params={"date_from": "2026-09-02", "date_to": "2026-09-03"}, headers=auth_headers
    ).json()
    assert period["total"] == 4  # período inclusivo nas duas pontas

    exits = client.get(
        RECORDS, params={"type": "EXIT", "sort": "recorded_at"}, headers=auth_headers
    ).json()
    assert [r["workday_date"] for r in exits["items"]] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert {r["employee_name"] for r in exits["items"]} == {"João", "Maria"}

    page = client.get(RECORDS, params={"page_size": 3, "page": 3}, headers=auth_headers).json()
    assert len(page["items"]) == 2
