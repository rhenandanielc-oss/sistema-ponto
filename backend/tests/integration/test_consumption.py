"""Consumo do funcionário (BUSINESS-RULES.md §12)."""

from fastapi.testclient import TestClient

from app.core import clock
from tests.integration.helpers import create_employee, local
from tests.integration.test_kiosk_biometrics import device, enroll, identify

ITEMS = "/api/v1/consumption-items"


def item(client: TestClient, headers, name: str, price_cents: int) -> int:
    response = client.post(ITEMS, json={"name": name, "price_cents": price_cents}, headers=headers)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def consume(client: TestClient, headers, employee: int, **body):
    return client.post(f"/api/v1/employees/{employee}/consumption", json=body, headers=headers)


def test_consumption_is_added_to_the_pay_cycle(client: TestClient, auth_headers) -> None:
    clock.freeze(local(10, "12:00"))
    joao = create_employee(client, auth_headers, payday=5)  # ciclo 06/09–05/10
    refri = item(client, auth_headers, "Refrigerante lata", 600)

    first = consume(client, auth_headers, joao, item_id=refri, quantity=2)
    assert first.status_code == 201, first.text
    assert (first.json()["description"], first.json()["total_cents"]) == ("Refrigerante lata", 1200)
    assert first.json()["entry_date"] == "2026-09-10"

    # Preço novo não muda o que já foi lançado.
    client.patch(f"{ITEMS}/{refri}", json={"price_cents": 700}, headers=auth_headers)
    assert consume(client, auth_headers, joao, item_id=refri).json()["total_cents"] == 700
    avulso = consume(
        client,
        auth_headers,
        joao,
        description="Salgado",
        unit_price_cents=550,
        entry_date="2026-09-11",
    )
    assert avulso.status_code == 201, avulso.text
    errado = consume(client, auth_headers, joao, item_id=refri).json()
    canceled = client.post(
        f"/api/v1/consumption/{errado['id']}/cancel",
        json={"reason": "Lançado duas vezes"},
        headers=auth_headers,
    )
    assert canceled.status_code == 200 and canceled.json()["canceled_at"] is not None
    again = client.post(
        f"/api/v1/consumption/{errado['id']}/cancel",
        json={"reason": "De novo"},
        headers=auth_headers,
    )
    assert again.status_code == 409

    listing = client.get(f"/api/v1/employees/{joao}/consumption", headers=auth_headers).json()
    assert len(listing["items"]) == 4
    assert listing["total_cents"] == 1200 + 700 + 550

    payroll = client.get(f"/api/v1/employees/{joao}/payroll", headers=auth_headers).json()
    assert payroll["consumption_cents"] == 2450
    # Consumo fora do ciclo não entra.
    consume(client, auth_headers, joao, item_id=refri, entry_date="2026-09-05")
    payroll = client.get(f"/api/v1/employees/{joao}/payroll", headers=auth_headers).json()
    assert payroll["consumption_cents"] == 2450

    summary = client.get("/api/v1/payroll", headers=auth_headers).json()["items"]
    assert summary[0]["consumption_cents"] == 2450


def test_consumption_validation(client: TestClient, auth_headers) -> None:
    joao = create_employee(client, auth_headers)
    refri = item(client, auth_headers, "Refrigerante", 600)
    assert (
        client.post(
            ITEMS, json={"name": "refrigerante", "price_cents": 500}, headers=auth_headers
        ).status_code
        == 409
    )
    assert (
        client.post(
            ITEMS, json={"name": "Água", "price_cents": 0}, headers=auth_headers
        ).status_code
        == 422
    )

    assert consume(client, auth_headers, joao).status_code == 422  # nem item nem avulso
    both = consume(client, auth_headers, joao, item_id=refri, description="X", unit_price_cents=1)
    assert both.status_code == 422
    assert consume(client, auth_headers, joao, item_id=refri, quantity=0).status_code == 422
    assert consume(client, auth_headers, joao, item_id=999).status_code == 404
    assert consume(client, auth_headers, 999, item_id=refri).status_code == 404

    client.patch(f"{ITEMS}/{refri}", json={"is_active": False}, headers=auth_headers)
    assert consume(client, auth_headers, joao, item_id=refri).status_code == 409
    active = client.get(ITEMS, params={"include_inactive": False}, headers=auth_headers).json()
    assert active == []


def test_employee_sees_own_consumption_at_the_kiosk(client: TestClient, auth_headers) -> None:
    clock.freeze(local(10, "12:00"))
    joao = create_employee(client, auth_headers, payday=5)
    assert enroll(client, auth_headers, joao, "joao").status_code == 201
    kiosk = device(client, auth_headers)
    refri = item(client, auth_headers, "Refrigerante", 600)
    consume(client, auth_headers, joao, item_id=refri, quantity=3)

    token = identify(client, kiosk, b"FACE:joao#camera").json()["identification_token"]
    bank = client.post(
        "/api/v1/kiosk/hour-bank", json={"identification_token": token}, headers=kiosk
    ).json()
    assert bank["pay_period_consumption_cents"] == 1800
