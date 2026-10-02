"""Feriados, terminais (kiosk) e configurações."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, full_day, local

HOLIDAYS = "/api/v1/holidays"


def test_holiday_crud_and_duplicates(client: TestClient, auth_headers) -> None:
    created = client.post(
        HOLIDAYS, json={"date": "2026-11-20", "name": "Consciência Negra"}, headers=auth_headers
    )
    assert created.status_code == 201
    holiday_id = created.json()["id"]

    duplicate = client.post(
        HOLIDAYS, json={"date": "2026-11-20", "name": "Outro"}, headers=auth_headers
    )
    assert duplicate.status_code == 409

    client.post(
        HOLIDAYS,
        json={"date": "2020-12-25", "name": "Natal", "recurring": True},
        headers=auth_headers,
    )
    recurring_dup = client.post(
        HOLIDAYS,
        json={"date": "2026-12-25", "name": "Natal 2", "recurring": True},
        headers=auth_headers,
    )
    assert recurring_dup.status_code == 409

    listing = client.get(
        HOLIDAYS, params={"date_from": "2026-01-01", "date_to": "2026-12-31"}, headers=auth_headers
    )
    assert {h["name"] for h in listing.json()} == {"Consciência Negra", "Natal"}

    renamed = client.patch(
        f"{HOLIDAYS}/{holiday_id}", json={"name": "Dia da Consciência Negra"}, headers=auth_headers
    )
    assert renamed.json()["name"] == "Dia da Consciência Negra"

    assert client.delete(f"{HOLIDAYS}/{holiday_id}", headers=auth_headers).status_code == 204
    assert client.delete(f"{HOLIDAYS}/{holiday_id}", headers=auth_headers).status_code == 404


def test_holiday_changes_calculation(client: TestClient, auth_headers, db: Session) -> None:
    employee = create_employee(client, auth_headers)
    clock.freeze(local(30, "12:00"))
    url = f"/api/v1/employees/{employee}/workdays"
    params = {"date_from": "2026-09-08", "date_to": "2026-09-08"}
    assert (
        client.get(url, params=params, headers=auth_headers).json()["days"][0]["status"] == "ABSENT"
    )
    client.post(
        HOLIDAYS, json={"date": "2026-09-08", "name": "Feriado municipal"}, headers=auth_headers
    )
    day = client.get(url, params=params, headers=auth_headers).json()["days"][0]
    assert (day["day_type"], day["status"], day["balance_minutes"]) == ("HOLIDAY", "NONE", 0)


def test_device_token_is_shown_once_and_authorizes_kiosk(client: TestClient, auth_headers) -> None:
    created = client.post("/api/v1/devices", json={"name": "Recepção"}, headers=auth_headers)
    assert created.status_code == 201
    token = created.json()["token"]
    assert len(token) >= 40

    listing = client.get("/api/v1/devices", headers=auth_headers).json()
    assert "token" not in listing[0] and "token_hash" not in listing[0]

    kiosk = {"Authorization": f"Device {token}"}
    ping = client.get("/api/v1/kiosk/ping", headers=kiosk)
    assert ping.status_code == 200
    assert ping.json()["device"] == "Recepção"
    assert client.get("/api/v1/devices", headers=auth_headers).json()[0]["last_seen_at"] is not None

    # Token de dispositivo não abre rotas administrativas.
    assert client.get("/api/v1/employees", headers=kiosk).status_code == 401

    device_id = created.json()["id"]
    rotated = client.post(f"/api/v1/devices/{device_id}/rotate-token", headers=auth_headers).json()
    assert client.get("/api/v1/kiosk/ping", headers=kiosk).status_code == 403
    new_kiosk = {"Authorization": f"Device {rotated['token']}"}
    assert client.get("/api/v1/kiosk/ping", headers=new_kiosk).status_code == 200

    # R15: terminal desativado.
    client.post(f"/api/v1/devices/{device_id}/deactivate", headers=auth_headers)
    denied = client.get("/api/v1/kiosk/ping", headers=new_kiosk)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "DEVICE_NOT_AUTHORIZED")


def test_settings_defaults_and_update(client: TestClient, auth_headers, db: Session) -> None:
    defaults = client.get("/api/v1/settings", headers=auth_headers).json()
    assert defaults["tolerance_per_mark_minutes"] == 5
    assert defaults["night_start"] == "22:00:00"

    invalid = client.patch(
        "/api/v1/settings", json={"tolerance_daily_minutes": -1}, headers=auth_headers
    )
    assert invalid.status_code == 422

    updated = client.patch(
        "/api/v1/settings",
        json={"tolerance_daily_minutes": 0, "tolerance_per_mark_minutes": 0},
        headers=auth_headers,
    )
    assert updated.json()["tolerance_daily_minutes"] == 0

    # Sem tolerância, 3 minutos de atraso passam a contar.
    employee = create_employee(client, auth_headers)
    full_day(db, employee, 1, "08:03", "12:00", "13:00", "17:00")
    clock.freeze(local(2, "07:00"))
    day = client.get(
        f"/api/v1/employees/{employee}/workdays",
        params={"date_from": "2026-09-01", "date_to": "2026-09-01"},
        headers=auth_headers,
    ).json()["days"][0]
    assert (day["late_minutes"], day["balance_minutes"]) == (3, -3)
