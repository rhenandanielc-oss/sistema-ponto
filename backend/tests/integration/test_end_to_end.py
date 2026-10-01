"""Fluxo completo de um mês de trabalho pela API, do cadastro ao banco de horas."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from tests.conftest import login
from tests.integration.helpers import full_day, local, punch


def test_month_of_work(client: TestClient, admin, db: Session) -> None:
    token = login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Administrador cadastra o funcionário: nome, dias, horário fixo e almoço.
    response = client.post(
        "/api/v1/employees",
        json={
            "name": "João",
            "registration_number": "100",
            "hire_date": "2026-09-01",
            "payday": 5,
            "schedule": {
                "weekdays": ["segunda", "terça", "quarta", "quinta", "sexta"],
                "start_time": "08:00",
                "end_time": "16:00",
                "lunch_minutes": 60,
            },
        },
        headers=headers,
    )
    assert response.status_code == 201
    joao = response.json()["id"]

    # 2. Feriado e terminal.
    client.post(
        "/api/v1/holidays", json={"date": "2026-09-07", "name": "Independência"}, headers=headers
    )
    device = client.post("/api/v1/devices", json={"name": "Recepção"}, headers=headers).json()
    assert (
        client.get(
            "/api/v1/kiosk/ping", headers={"Authorization": f"Device {device['token']}"}
        ).status_code
        == 200
    )

    # 3. Primeira semana: (07:00 = carga de 08:00-16:00 menos 1 h de almoço)
    full_day(db, joao, 1, "08:00", "12:00", "13:00", "16:00")  # ter: 0
    full_day(db, joao, 2, "08:00", "11:30", "12:00", "16:00")  # qua: almoço de 30 min, +30
    full_day(db, joao, 3, "08:15", "12:00", "13:00", "16:00")  # qui: atraso 15, -15
    punch(db, joao, "ENTRY", local(4, "08:00"))  # sex: esqueceu a saída
    full_day(db, joao, 5, "09:00", "13:00")  # sáb: fora da escala, +240
    # seg 07/09 feriado; ter 08/09 falta (-420)

    # 4. Administrador corrige a saída esquecida de sexta.
    clock.freeze(local(9, "09:00"))
    adjust = client.post(
        "/api/v1/time-records/adjustments",
        json={
            "kind": "ADD",
            "employee_id": joao,
            "type": "EXIT",
            "recorded_at": local(4, "16:00").isoformat(),
            "reason": "Funcionário esqueceu de bater a saída",
        },
        headers=headers,
    )
    assert adjust.status_code == 201

    # 5. Banco de horas da semana.
    bank = client.get(
        f"/api/v1/employees/{joao}/hour-bank",
        params={"date_from": "2026-09-01", "date_to": "2026-09-08"},
        headers=headers,
    ).json()
    by_date = {d["date"]: d for d in bank["days"]}
    assert by_date["2026-09-01"]["balance_minutes"] == 0
    assert by_date["2026-09-02"]["balance_minutes"] == 30
    assert (by_date["2026-09-03"]["late_minutes"], by_date["2026-09-03"]["balance_minutes"]) == (
        15,
        -15,
    )
    # Sexta sem almoço: 8 h trabalhadas, +60 e alerta de intervalo insuficiente.
    assert by_date["2026-09-04"]["balance_minutes"] == 60
    assert "INSUFFICIENT_BREAK" in by_date["2026-09-04"]["flags"]
    assert by_date["2026-09-05"]["overtime_minutes"] == 240
    assert by_date["2026-09-06"]["status"] == "NONE"
    assert by_date["2026-09-07"]["day_type"] == "HOLIDAY"
    assert by_date["2026-09-08"]["status"] == "ABSENT"
    assert bank["closing_balance_minutes"] == 0 + 30 - 15 + 60 + 240 - 420

    # 6. Tudo ficou na auditoria.
    audit = client.get(
        "/api/v1/audit-logs", params={"action": "record.", "page_size": 200}, headers=headers
    ).json()
    actions = [i["action"] for i in audit["items"]]
    assert actions.count("record.create") == 4 + 4 + 4 + 1 + 2
    assert actions.count("record.adjust_add") == 1
