"""Funcionários e horário fixo (TEST-PLAN.md §6)."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock

EMPLOYEES = "/api/v1/employees"

STANDARD_DAY = {"start_time": "08:00", "end_time": "17:00", "lunch_minutes": 60}


def week(**overrides: Any) -> dict[str, Any]:
    """Segunda a sexta 08:00–17:00 com 1 h de almoço, com sobrescritas por campo."""
    return {"days": [{"weekday": w, **STANDARD_DAY, **overrides} for w in range(5)]}


def payload(**overrides: Any) -> dict[str, Any]:
    data = {
        "name": "Maria Souza",
        "registration_number": "001",
        "cpf": "529.982.247-25",
        "hire_date": "2026-09-01",
        "payday": 5,
        "schedule": week(),
    }
    data.update(overrides)
    return data


def create(client: TestClient, headers: dict[str, str], **overrides: Any) -> Any:
    return client.post(EMPLOYEES, json=payload(**overrides), headers=headers)


def test_create_employee_with_fixed_schedule(client: TestClient, auth_headers) -> None:
    clock.freeze(datetime(2026, 9, 10, 12, tzinfo=UTC))
    response = create(client, auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Maria Souza"
    assert body["cpf"] == "52998224725"
    assert body["status"] == "ACTIVE"
    schedule = body["current_schedule"]
    assert schedule["valid_from"] == "2026-09-01"
    assert schedule["valid_to"] is None
    assert [d["weekday"] for d in schedule["days"]] == [0, 1, 2, 3, 4]
    assert schedule["days"][0] == {
        "weekday": 0,
        "start_time": "08:00:00",
        "end_time": "17:00:00",
        "lunch_minutes": 60,
        "planned_minutes": 480,
    }


def test_simple_schedule_form_like_joao(client: TestClient, auth_headers) -> None:
    """Nome: João / Horário fixo: 08:00 - 16:00 (almoço padrão de 1 h, segunda a sexta)."""
    response = create(
        client, auth_headers, name="João", schedule={"start_time": "08:00", "end_time": "16:00"}
    )
    assert response.status_code == 201, response.text
    days = response.json()["current_schedule"]["days"]
    assert [d["weekday"] for d in days] == [0, 1, 2, 3, 4]
    assert {
        (d["start_time"], d["end_time"], d["lunch_minutes"], d["planned_minutes"]) for d in days
    } == {("08:00:00", "16:00:00", 60, 420)}


def test_simple_schedule_form_with_custom_days_and_lunch(client: TestClient, auth_headers) -> None:
    schedule = {"start_time": "08:00", "end_time": "12:00", "lunch_minutes": 0, "weekdays": [5]}
    days = create(client, auth_headers, schedule=schedule).json()["current_schedule"]["days"]
    assert [(d["weekday"], d["planned_minutes"]) for d in days] == [(5, 240)]


def test_planned_minutes_for_night_and_no_lunch_days(client: TestClient, auth_headers) -> None:
    schedule = {
        "days": [
            {"weekday": 0, "start_time": "22:00", "end_time": "06:00"},
            {"weekday": 5, "start_time": "08:00", "end_time": "12:00", "lunch_minutes": 0},
        ]
    }
    body = create(client, auth_headers, schedule=schedule).json()
    planned = {d["weekday"]: d["planned_minutes"] for d in body["current_schedule"]["days"]}
    assert planned == {0: 420, 5: 240}


def test_schedule_is_required_and_validated(client: TestClient, auth_headers) -> None:
    missing = client.post(
        EMPLOYEES,
        json={k: v for k, v in payload().items() if k != "schedule"},
        headers=auth_headers,
    )
    assert missing.status_code == 422

    empty = create(client, auth_headers, schedule={"days": []})
    assert empty.status_code == 422

    lunch_too_long = create(client, auth_headers, schedule=week(lunch_minutes=540))
    assert lunch_too_long.status_code == 422
    assert "almoço" in str(lunch_too_long.json()["error"]["details"])

    negative_lunch = create(client, auth_headers, schedule=week(lunch_minutes=-5))
    assert negative_lunch.status_code == 422

    repeated = create(
        client,
        auth_headers,
        schedule={"days": [{"weekday": 1, **STANDARD_DAY}, {"weekday": 1, **STANDARD_DAY}]},
    )
    assert repeated.status_code == 422

    too_long = create(client, auth_headers, schedule=week(start_time="05:00", end_time="23:00"))
    assert too_long.status_code == 422

    bad_weekday = create(client, auth_headers, schedule={"days": [{"weekday": 7, **STANDARD_DAY}]})
    assert bad_weekday.status_code == 422


def test_invalid_cpf_and_blank_name(client: TestClient, auth_headers) -> None:
    assert create(client, auth_headers, cpf="123.456.789-00").status_code == 422
    assert create(client, auth_headers, name="   ").status_code == 422


def test_duplicate_registration_and_cpf(client: TestClient, auth_headers) -> None:
    assert create(client, auth_headers).status_code == 201
    dup_registration = create(client, auth_headers, cpf=None)
    assert dup_registration.status_code == 409
    dup_cpf = create(client, auth_headers, registration_number="002")
    assert dup_cpf.status_code == 409
    assert create(client, auth_headers, registration_number="002", cpf=None).status_code == 201


def test_search_pagination_and_sorting(client: TestClient, auth_headers) -> None:
    for number, name in [("003", "Carlos"), ("001", "ana Lima"), ("002", "Bruno")]:
        create(client, auth_headers, registration_number=number, name=name, cpf=None)

    page = client.get(EMPLOYEES, params={"page_size": 2}, headers=auth_headers).json()
    assert page["total"] == 3
    assert [e["name"] for e in page["items"]] == ["ana Lima", "Bruno"]

    page2 = client.get(EMPLOYEES, params={"page_size": 2, "page": 2}, headers=auth_headers).json()
    assert [e["name"] for e in page2["items"]] == ["Carlos"]

    by_number_desc = client.get(
        EMPLOYEES, params={"sort": "-registration_number"}, headers=auth_headers
    )
    assert [e["registration_number"] for e in by_number_desc.json()["items"]] == [
        "003",
        "002",
        "001",
    ]

    search_name = client.get(EMPLOYEES, params={"q": "ANA"}, headers=auth_headers).json()
    assert [e["name"] for e in search_name["items"]] == ["ana Lima"]

    search_number = client.get(EMPLOYEES, params={"q": "003"}, headers=auth_headers).json()
    assert [e["name"] for e in search_number["items"]] == ["Carlos"]

    bad_sort = client.get(EMPLOYEES, params={"sort": "cpf"}, headers=auth_headers)
    assert bad_sort.status_code == 422

    too_big = client.get(EMPLOYEES, params={"page_size": 500}, headers=auth_headers)
    assert too_big.status_code == 422


def test_deactivate_keeps_data_and_filters_by_status(client: TestClient, auth_headers) -> None:
    employee = create(client, auth_headers).json()
    create(client, auth_headers, registration_number="002", cpf=None, name="Outro")

    response = client.post(f"{EMPLOYEES}/{employee['id']}/deactivate", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["current_schedule"] is not None

    inactive = client.get(EMPLOYEES, params={"status": "INACTIVE"}, headers=auth_headers).json()
    assert [e["id"] for e in inactive["items"]] == [employee["id"]]

    reactivated = client.post(f"{EMPLOYEES}/{employee['id']}/activate", headers=auth_headers)
    assert reactivated.json()["status"] == "ACTIVE"


def test_update_and_history(client: TestClient, auth_headers) -> None:
    employee = create(client, auth_headers).json()
    response = client.patch(
        f"{EMPLOYEES}/{employee['id']}",
        json={"name": "Maria S. Lima", "cpf": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Maria S. Lima"
    assert response.json()["cpf"] is None

    client.post(f"{EMPLOYEES}/{employee['id']}/deactivate", headers=auth_headers)

    history = client.get(f"{EMPLOYEES}/{employee['id']}/history", headers=auth_headers).json()
    assert [h["action"] for h in history["items"]] == [
        "employee.deactivate",
        "employee.update",
        "employee.create",
    ]
    update_entry = history["items"][1]
    assert update_entry["before"]["name"] == "Maria Souza"
    assert update_entry["after"]["name"] == "Maria S. Lima"
    assert update_entry["actor_type"] == "ADMIN"
    assert history["items"][2]["after"]["schedule"]["days"][0]["start_time"] == "08:00:00"


def test_update_rejects_invalid_dates_and_nulls(client: TestClient, auth_headers) -> None:
    employee = create(client, auth_headers).json()
    url = f"{EMPLOYEES}/{employee['id']}"
    assert (
        client.patch(url, json={"termination_date": "2026-08-01"}, headers=auth_headers).status_code
        == 422
    )
    assert client.patch(url, json={"name": None}, headers=auth_headers).status_code == 422
    ok = client.patch(url, json={"termination_date": "2026-12-31"}, headers=auth_headers)
    assert ok.json()["termination_date"] == "2026-12-31"


def test_changing_hire_date_moves_first_schedule(client: TestClient, auth_headers) -> None:
    employee = create(client, auth_headers).json()
    url = f"{EMPLOYEES}/{employee['id']}"
    client.patch(url, json={"hire_date": "2026-08-15"}, headers=auth_headers)
    schedules = client.get(f"{url}/schedules", headers=auth_headers).json()
    assert schedules[0]["valid_from"] == "2026-08-15"


def test_new_schedule_closes_previous_one(client: TestClient, auth_headers) -> None:
    clock.freeze(datetime(2026, 9, 20, 12, tzinfo=UTC))
    employee = create(client, auth_headers).json()
    url = f"{EMPLOYEES}/{employee['id']}/schedules"

    new = client.post(
        url,
        json={"valid_from": "2026-09-16", **week(start_time="09:00", end_time="16:00")},
        headers=auth_headers,
    )
    assert new.status_code == 201, new.text
    assert new.json()["days"][0]["planned_minutes"] == 360

    schedules = client.get(url, headers=auth_headers).json()
    assert [(s["valid_from"], s["valid_to"]) for s in schedules] == [
        ("2026-09-01", "2026-09-15"),
        ("2026-09-16", None),
    ]
    detail = client.get(f"{EMPLOYEES}/{employee['id']}", headers=auth_headers).json()
    assert detail["current_schedule"]["valid_from"] == "2026-09-16"

    # Visto a partir de 10/09, o horário vigente ainda é o primeiro.
    clock.freeze(datetime(2026, 9, 10, 12, tzinfo=UTC))
    detail = client.get(f"{EMPLOYEES}/{employee['id']}", headers=auth_headers).json()
    assert detail["current_schedule"]["valid_from"] == "2026-09-01"

    history = client.get(f"{EMPLOYEES}/{employee['id']}/history", headers=auth_headers).json()
    assert history["items"][0]["action"] == "employee.schedule_create"


def test_new_schedule_overlap_and_bounds(client: TestClient, auth_headers) -> None:
    employee = create(client, auth_headers).json()
    url = f"{EMPLOYEES}/{employee['id']}/schedules"

    same_start = client.post(url, json={"valid_from": "2026-09-01", **week()}, headers=auth_headers)
    assert same_start.status_code == 409
    assert same_start.json()["error"]["code"] == "SCHEDULE_OVERLAP"

    before_hire = client.post(
        url, json={"valid_from": "2026-08-01", **week()}, headers=auth_headers
    )
    assert before_hire.status_code == 409


def test_unknown_employee(client: TestClient, auth_headers) -> None:
    response = client.get(f"{EMPLOYEES}/999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


def test_database_rejects_overlapping_schedules(
    client: TestClient, auth_headers, db: Session
) -> None:
    """Última linha de defesa: a restrição EXCLUDE do banco."""
    employee = create(client, auth_headers).json()
    try:
        db.execute(
            text(
                "INSERT INTO employee_schedules (employee_id, valid_from) "
                "VALUES (:id, '2026-10-01')"
            ),
            {"id": employee["id"]},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("A sobreposição de vigências deveria ser rejeitada pelo banco")


def test_admin_types_name_days_schedule_and_lunch(client: TestClient, auth_headers) -> None:
    """Cadastro como o administrador digita: nome, dias de trabalho, horário fixo e almoço."""
    response = create(
        client,
        auth_headers,
        name="João",
        schedule={
            "weekdays": ["Segunda-feira", "terça", "QUA", "qui", "sex", "sábado"],
            "start_time": "08:00",
            "end_time": "16:00",
            "lunch_minutes": 30,
        },
    )
    assert response.status_code == 201, response.text
    days = response.json()["current_schedule"]["days"]
    assert [d["weekday"] for d in days] == [0, 1, 2, 3, 4, 5]
    assert {d["planned_minutes"] for d in days} == {450}  # 8 h - 30 min


def test_invalid_weekday_name(client: TestClient, auth_headers) -> None:
    response = create(
        client,
        auth_headers,
        schedule={"weekdays": ["segunda", "feriado"], "start_time": "08:00", "end_time": "16:00"},
    )
    assert response.status_code == 422
    assert "feriado" in str(response.json()["error"]["details"])
    empty = create(
        client, auth_headers, schedule={"weekdays": [], "start_time": "08:00", "end_time": "16:00"}
    )
    assert empty.status_code == 422
