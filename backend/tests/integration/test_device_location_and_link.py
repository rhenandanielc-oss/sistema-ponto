"""Link de ativação de uso único e trava por localização dos terminais (BUSINESS-RULES.md §4.7)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import clock
from tests.integration.helpers import create_employee, local
from tests.integration.test_kiosk_biometrics import KIOSK, enroll, photo

RESTAURANT = {"location_latitude": -23.55052, "location_longitude": -46.63331}
NEAR = {"latitude": "-23.5506", "longitude": "-46.6334", "accuracy_m": "20"}  # ~15 m
FAR = {"latitude": "-23.5700", "longitude": "-46.6500", "accuracy_m": "20"}  # ~2,4 km


def new_device(client: TestClient, headers, **extra: Any) -> tuple[int, dict[str, str]]:
    body = client.post("/api/v1/devices", json={"name": "Celular", **extra}, headers=headers).json()
    return body["id"], {"Authorization": f"Device {body['token']}"}


def identify_at(client: TestClient, kiosk, content: bytes, place: dict[str, str] | None):
    return client.post(f"{KIOSK}/identify", files=photo(content), data=place or {}, headers=kiosk)


@pytest.fixture
def setup(client: TestClient, auth_headers) -> None:
    clock.freeze(local(1, "07:58"))
    joao = create_employee(client, auth_headers, name="João")
    assert enroll(client, auth_headers, joao, "joao").status_code == 201


def test_activation_link_is_single_use_and_replaces_the_token(client: TestClient, auth_headers):
    device_id, old = new_device(client, auth_headers)
    link = client.post(f"/api/v1/devices/{device_id}/activation-link", headers=auth_headers)
    assert link.status_code == 201, link.text
    code = link.json()["code"]

    first = client.post(f"{KIOSK}/activate", json={"code": code})
    assert first.status_code == 200, first.text
    new = {"Authorization": f"Device {first.json()['token']}"}
    assert client.get(f"{KIOSK}/ping", headers=new).status_code == 200
    assert client.get(f"{KIOSK}/ping", headers=old).status_code == 403  # token antigo não vale mais

    again = client.post(f"{KIOSK}/activate", json={"code": code})
    assert (again.status_code, again.json()["error"]["code"]) == (403, "ACTIVATION_LINK_INVALID")


def test_activation_link_expires_and_inactive_devices_cannot_use_it(
    client: TestClient, auth_headers
):
    clock.freeze(local(1, "08:00"))
    device_id, _ = new_device(client, auth_headers)
    code = client.post(f"/api/v1/devices/{device_id}/activation-link", headers=auth_headers).json()[
        "code"
    ]
    clock.freeze(local(1, "08:00") + timedelta(hours=25))
    assert client.post(f"{KIOSK}/activate", json={"code": code}).status_code == 403

    clock.freeze(local(2, "08:00"))
    code = client.post(f"/api/v1/devices/{device_id}/activation-link", headers=auth_headers).json()[
        "code"
    ]
    client.post(f"/api/v1/devices/{device_id}/deactivate", headers=auth_headers)
    assert client.post(f"{KIOSK}/activate", json={"code": code}).status_code == 403
    assert client.post(f"{KIOSK}/activate", json={"code": "x" * 30}).status_code == 403


def test_new_link_invalidates_the_previous_one(client: TestClient, auth_headers):
    device_id, _ = new_device(client, auth_headers)
    url = f"/api/v1/devices/{device_id}/activation-link"
    first = client.post(url, headers=auth_headers).json()["code"]
    second = client.post(url, headers=auth_headers).json()["code"]
    assert client.post(f"{KIOSK}/activate", json={"code": first}).status_code == 403
    assert client.post(f"{KIOSK}/activate", json={"code": second}).status_code == 200


def test_device_without_location_rule_ignores_the_position(client: TestClient, auth_headers, setup):
    _, kiosk = new_device(client, auth_headers)
    assert client.get(f"{KIOSK}/ping", headers=kiosk).json()["require_location"] is False
    assert identify_at(client, kiosk, b"FACE:joao#1", None).status_code == 200


def test_location_rule_needs_the_restaurant_to_be_configured(
    client: TestClient, auth_headers, setup
):
    _, kiosk = new_device(client, auth_headers, require_location=True)
    response = identify_at(client, kiosk, b"FACE:joao#1", NEAR)
    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "LOCATION_NOT_CONFIGURED",
    )


def test_location_rule_blocks_identify_and_record_outside_the_radius(
    client: TestClient, auth_headers, setup
):
    client.patch(
        "/api/v1/settings", json={**RESTAURANT, "location_radius_meters": 150}, headers=auth_headers
    )
    _, kiosk = new_device(client, auth_headers, require_location=True)
    assert client.get(f"{KIOSK}/ping", headers=kiosk).json()["require_location"] is True

    def code(place: dict[str, str] | None) -> tuple[int, str | None]:
        r = identify_at(client, kiosk, b"FACE:joao#1", place)
        return r.status_code, r.json().get("error", {}).get("code")

    assert code(None) == (422, "LOCATION_REQUIRED")
    assert code({**NEAR, "accuracy_m": "500"}) == (422, "LOCATION_IMPRECISE")
    assert code(FAR) == (403, "LOCATION_OUT_OF_RANGE")
    ok = identify_at(client, kiosk, b"FACE:joao#1", NEAR)
    assert ok.status_code == 200, ok.text

    token = ok.json()["identification_token"]
    body = {"identification_token": token, "type": "ENTRY"}
    far = {"latitude": -23.57, "longitude": -46.65, "accuracy_m": 20}
    blocked = client.post(f"{KIOSK}/records", json={**body, **far}, headers=kiosk)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (403, "LOCATION_OUT_OF_RANGE")
    near = {"latitude": -23.5506, "longitude": -46.6334, "accuracy_m": 20}
    assert client.post(f"{KIOSK}/records", json={**body, **near}, headers=kiosk).status_code == 201


def test_admin_can_toggle_the_location_rule_per_device(client: TestClient, auth_headers):
    device_id, _ = new_device(client, auth_headers)
    on = client.patch(
        f"/api/v1/devices/{device_id}", json={"require_location": True}, headers=auth_headers
    )
    assert on.json()["require_location"] is True
    listed = {d["id"]: d for d in client.get("/api/v1/devices", headers=auth_headers).json()}
    assert listed[device_id]["require_location"] is True
    off = client.patch(
        f"/api/v1/devices/{device_id}", json={"require_location": False}, headers=auth_headers
    )
    assert off.json()["require_location"] is False


def test_distance_helper_is_about_right() -> None:
    from app.services.location_service import distance_meters

    assert distance_meters(-23.55052, -46.63331, -23.55052, -46.63331) == 0
    one_degree_lat = distance_meters(0, 0, 1, 0)
    assert 110_000 < one_degree_lat < 112_000


def test_locate_accepts_pasted_coordinates_without_network(client: TestClient, auth_headers):
    ok = client.post(
        "/api/v1/settings/locate", json={"query": " -22.95306, -46.54222 "}, headers=auth_headers
    )
    assert ok.status_code == 200, ok.text
    assert (ok.json()["latitude"], ok.json()["longitude"]) == (-22.95306, -46.54222)
    assert client.post(
        "/api/v1/settings/locate", json={"query": "95.0, -46.5"}, headers=auth_headers
    ).status_code in (
        422,
        502,
    )


def test_locate_reads_google_maps_links_and_addresses(
    monkeypatch, client: TestClient, auth_headers
):
    from app.services import location_service

    full = "https://www.google.com/maps/place/N33/@-22.9500,-46.5400,17z/data=!3m1!4b1!4d!3d-22.9512345!4d-46.5412345"
    pin = client.post("/api/v1/settings/locate", json={"query": full}, headers=auth_headers).json()
    assert (pin["latitude"], pin["longitude"]) == (
        -22.9512345,
        -46.5412345,
    )  # o alfinete, não o centro

    short = "https://maps.app.goo.gl/abc123"
    monkeypatch.setattr(
        location_service,
        "_next_hop",
        lambda url: "https://www.google.com/maps/@-22.9,-46.5,15z" if "goo.gl" in url else None,
    )
    via_short = client.post(
        "/api/v1/settings/locate", json={"query": short}, headers=auth_headers
    ).json()
    assert (via_short["latitude"], via_short["longitude"]) == (-22.9, -46.5)

    other = client.post(
        "/api/v1/settings/locate", json={"query": "https://exemplo.com/x"}, headers=auth_headers
    )
    assert other.status_code == 422  # só links do Google Maps são seguidos

    monkeypatch.setattr(
        location_service,
        "_fetch_json",
        lambda url: [
            {
                "lat": "-22.9531",
                "lon": "-46.5422",
                "display_name": "Av. Dr. Geraldo, Bragança Paulista",
            }
        ],
    )
    address = client.post(
        "/api/v1/settings/locate",
        json={"query": "Avenida Doutor Geraldo de Assis Gonçalves, Bragança Paulista"},
        headers=auth_headers,
    ).json()
    assert (address["latitude"], address["longitude"]) == (-22.9531, -46.5422)

    monkeypatch.setattr(location_service, "_fetch_json", lambda url: [])
    nothing = client.post(
        "/api/v1/settings/locate", json={"query": "lugar que não existe"}, headers=auth_headers
    )
    assert (nothing.status_code, nothing.json()["error"]["code"]) == (422, "LOCATION_NOT_FOUND")


def test_locate_requires_an_admin(client: TestClient) -> None:
    assert client.post("/api/v1/settings/locate", json={"query": "-22.9, -46.5"}).status_code == 401


def test_locate_refuses_points_outside_brazil_like_a_missing_minus_sign(
    client: TestClient, auth_headers
):
    wrong = client.post(
        "/api/v1/settings/locate", json={"query": "22.968140, -46.544648"}, headers=auth_headers
    )
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "LOCATION_OUTSIDE_BRAZIL")
    right = client.post(
        "/api/v1/settings/locate", json={"query": "-22.968140, -46.544648"}, headers=auth_headers
    )
    assert right.status_code == 200, right.text
