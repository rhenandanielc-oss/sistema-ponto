"""Biometria e terminal de ponto — TEST-PLAN.md A11–A13 e §7.

Usa o motor facial falso (FACE_ENGINE=fake): b"FACE:<pessoa>" representa uma foto daquela pessoa.
"""

import os
import tempfile
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.models import AuditLog, BiometricTemplate, KioskIdentification
from app.services import biometric_service, maintenance_service
from tests.integration.helpers import create_employee, local

KIOSK = "/api/v1/kiosk"


def photo(content: bytes) -> dict[str, Any]:
    return {"image": ("rosto.jpg", content, "image/jpeg")}


def device(client: TestClient, headers: dict[str, str], name: str = "Recepção") -> dict[str, str]:
    token = client.post("/api/v1/devices", json={"name": name}, headers=headers).json()["token"]
    return {"Authorization": f"Device {token}"}


def enroll(client: TestClient, headers: dict[str, str], employee: int, person: str) -> Any:
    client.post(f"/api/v1/employees/{employee}/biometric-consent", json={}, headers=headers)
    return client.post(
        f"/api/v1/employees/{employee}/biometric-templates",
        files=photo(f"FACE:{person}#cadastro".encode()),
        headers=headers,
    )


def identify(client: TestClient, kiosk: dict[str, str], content: bytes) -> Any:
    return client.post(f"{KIOSK}/identify", files=photo(content), headers=kiosk)


@pytest.fixture
def setup(client: TestClient, auth_headers) -> dict[str, Any]:
    clock.freeze(local(1, "07:58"))
    joao = create_employee(client, auth_headers, name="João")
    maria = create_employee(client, auth_headers, registration="002", name="Maria")
    assert enroll(client, auth_headers, joao, "joao").status_code == 201
    assert enroll(client, auth_headers, maria, "maria").status_code == 201
    return {"joao": joao, "maria": maria, "kiosk": device(client, auth_headers)}


def test_full_flow_identify_then_punch(client: TestClient, setup) -> None:
    kiosk = setup["kiosk"]
    response = identify(client, kiosk, b"FACE:joao#camera")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employee_name"] == "João"
    assert body["allowed_types"] == ["ENTRY"]
    assert body["expires_in"] == 60

    clock.freeze(local(1, "07:58") + timedelta(seconds=5))
    record = client.post(
        f"{KIOSK}/records",
        json={"identification_token": body["identification_token"], "type": "ENTRY"},
        headers=kiosk,
    )
    assert record.status_code == 201, record.text
    assert record.json()["employee_name"] == "João"
    assert record.json()["recorded_at"] == "2026-09-01T07:58:05-03:00"  # horário do servidor

    # A13: o mesmo token não serve para outra batida.
    again = client.post(
        f"{KIOSK}/records",
        json={"identification_token": body["identification_token"], "type": "EXIT"},
        headers=kiosk,
    )
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "IDENTIFICATION_REQUIRED"

    # Próxima identificação já oferece os botões seguintes.
    clock.freeze(local(1, "12:00"))
    assert identify(client, kiosk, b"FACE:joao#2").json()["allowed_types"] == ["LUNCH_EXIT", "EXIT"]


def test_record_stores_device_and_score(client: TestClient, setup, auth_headers) -> None:
    kiosk = setup["kiosk"]
    token = identify(client, kiosk, b"FACE:maria#x").json()["identification_token"]
    client.post(
        f"{KIOSK}/records", json={"identification_token": token, "type": "ENTRY"}, headers=kiosk
    )
    history = client.get("/api/v1/time-records", headers=auth_headers).json()["items"][0]
    assert history["employee_name"] == "Maria"
    assert history["source"] == "KIOSK"
    assert history["device_id"] is not None
    assert history["face_match_score"] == pytest.approx(1.0, abs=1e-3)


def test_a11_expired_or_foreign_token(client: TestClient, setup, auth_headers) -> None:
    kiosk = setup["kiosk"]
    token = identify(client, kiosk, b"FACE:joao#x").json()["identification_token"]
    other_kiosk = device(client, auth_headers, "Fábrica")
    foreign = client.post(
        f"{KIOSK}/hour-bank", json={"identification_token": token}, headers=other_kiosk
    )
    assert foreign.status_code == 401  # token de outro terminal

    clock.freeze(local(1, "07:58") + timedelta(seconds=61))
    expired = client.post(f"{KIOSK}/hour-bank", json={"identification_token": token}, headers=kiosk)
    assert (expired.status_code, expired.json()["error"]["code"]) == (
        401,
        "IDENTIFICATION_REQUIRED",
    )
    expired_record = client.post(
        f"{KIOSK}/records", json={"identification_token": token, "type": "ENTRY"}, headers=kiosk
    )
    assert expired_record.status_code == 401


def test_a12_hour_bank_shows_only_identified_employee(client: TestClient, setup) -> None:
    kiosk = setup["kiosk"]
    token = identify(client, kiosk, b"FACE:maria#x").json()["identification_token"]
    first = client.post(f"{KIOSK}/hour-bank", json={"identification_token": token}, headers=kiosk)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["employee_name"] == "Maria"
    assert body["screen_seconds"] == 30
    assert body["pay_period_end"] == "2026-09-05"
    # A consulta não consome o token: pode olhar e depois bater o ponto.
    record = client.post(
        f"{KIOSK}/records", json={"identification_token": token, "type": "ENTRY"}, headers=kiosk
    )
    assert record.status_code == 201
    # Não existe forma de pedir o banco de outra pessoa: o corpo não aceita id de funcionário.
    attempt = client.post(
        f"{KIOSK}/hour-bank",
        json={"identification_token": token, "employee_id": setup["joao"]},
        headers=kiosk,
    )
    assert attempt.json().get("employee_name") in (None, "Maria")


def test_face_quality_errors(client: TestClient, setup, db: Session) -> None:
    kiosk = setup["kiosk"]
    for content, status, code in [
        (b"NOFACE", 422, "FACE_NOT_FOUND"),
        (b"MULTI", 422, "MULTIPLE_FACES"),
        (b"BLUR", 422, "LOW_QUALITY"),
        (b"FACE:desconhecido", 404, "FACE_NOT_RECOGNIZED"),
    ]:
        response = identify(client, kiosk, content)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    wrong_type = client.post(
        f"{KIOSK}/identify", files={"image": ("x.gif", b"GIF89a", "image/gif")}, headers=kiosk
    )
    assert wrong_type.json()["error"]["code"] == "INVALID_IMAGE"
    failures = db.scalars(select(AuditLog).where(AuditLog.action == "kiosk.identify_failed")).all()
    assert [f.after["code"] for f in failures] == [  # type: ignore[index]
        "FACE_NOT_FOUND",
        "MULTIPLE_FACES",
        "LOW_QUALITY",
        "FACE_NOT_RECOGNIZED",
    ]


def test_inactive_employee_is_not_recognized(
    client: TestClient, setup, auth_headers, db: Session
) -> None:
    client.post(f"/api/v1/employees/{setup['joao']}/deactivate", headers=auth_headers)
    response = identify(client, setup["kiosk"], b"FACE:joao#x")
    assert response.json()["error"]["code"] == "FACE_NOT_RECOGNIZED"
    # Desativar exclui os templates (BIOMETRICS.md §6).
    active = db.scalars(
        select(BiometricTemplate).where(
            BiometricTemplate.employee_id == setup["joao"], BiometricTemplate.deleted_at.is_(None)
        )
    ).all()
    assert active == []


def test_revoked_consent_and_deleted_templates(client: TestClient, setup, auth_headers) -> None:
    joao, maria, kiosk = setup["joao"], setup["maria"], setup["kiosk"]
    assert (
        client.delete(
            f"/api/v1/employees/{joao}/biometric-consent", headers=auth_headers
        ).status_code
        == 204
    )
    assert identify(client, kiosk, b"FACE:joao#x").status_code == 404
    status = client.get(f"/api/v1/employees/{joao}/biometric-status", headers=auth_headers).json()
    assert (status["consent"], status["templates"], status["ready"]) == (False, 0, False)

    assert (
        client.delete(
            f"/api/v1/employees/{maria}/biometric-templates", headers=auth_headers
        ).status_code
        == 204
    )
    assert identify(client, kiosk, b"FACE:maria#x").status_code == 404


def test_enroll_requires_consent_and_limits_photos(client: TestClient, auth_headers) -> None:
    employee = create_employee(client, auth_headers)
    url = f"/api/v1/employees/{employee}/biometric-templates"
    no_consent = client.post(url, files=photo(b"FACE:ana"), headers=auth_headers)
    assert (no_consent.status_code, no_consent.json()["error"]["code"]) == (409, "CONSENT_REQUIRED")

    client.post(f"/api/v1/employees/{employee}/biometric-consent", json={}, headers=auth_headers)
    bad = client.post(url, files=photo(b"NOFACE"), headers=auth_headers)
    assert bad.json()["error"]["code"] == "FACE_NOT_FOUND"
    for i in range(5):
        ok = client.post(url, files=photo(f"FACE:ana#{i}".encode()), headers=auth_headers)
        assert ok.status_code == 201
    assert ok.json()["templates"] == 5
    assert ok.json()["ready"] is True
    sixth = client.post(url, files=photo(b"FACE:ana#6"), headers=auth_headers)
    assert sixth.status_code == 409


def test_no_image_is_written_to_disk_or_database(
    client: TestClient, auth_headers, db: Session
) -> None:
    employee = create_employee(client, auth_headers)
    client.post(f"/api/v1/employees/{employee}/biometric-consent", json={}, headers=auth_headers)
    tmp = tempfile.gettempdir()
    before = set(os.listdir(tmp))
    content = b"FACE:ana#marcador-unico-da-imagem"
    client.post(
        f"/api/v1/employees/{employee}/biometric-templates",
        files=photo(content),
        headers=auth_headers,
    )
    assert set(os.listdir(tmp)) - before == set()
    template = db.scalars(select(BiometricTemplate)).one()
    assert content not in template.ciphertext
    assert len(template.ciphertext) == 128 * 4 + 16  # vetor float32 + tag GCM
    audit_text = " ".join(str(a.after) for a in db.scalars(select(AuditLog)).all())
    assert "marcador-unico" not in audit_text


def test_kiosk_rejection_keeps_token_usable(client: TestClient, setup) -> None:
    kiosk = setup["kiosk"]
    token = identify(client, kiosk, b"FACE:joao#x").json()["identification_token"]
    wrong = client.post(
        f"{KIOSK}/records", json={"identification_token": token, "type": "EXIT"}, headers=kiosk
    )
    assert wrong.json()["error"]["code"] == "INVALID_SEQUENCE"
    # O erro de sequência não gasta o token: o funcionário escolhe o botão certo.
    right = client.post(
        f"{KIOSK}/records", json={"identification_token": token, "type": "ENTRY"}, headers=kiosk
    )
    assert right.status_code == 201


def test_purge_deleted_templates(client: TestClient, setup, auth_headers, db: Session) -> None:
    client.delete(f"/api/v1/employees/{setup['joao']}/biometric-templates", headers=auth_headers)
    assert biometric_service.purge_deleted(db) == 0  # ainda dentro dos 30 dias
    clock.freeze(local(1, "07:58") + timedelta(days=31))
    assert biometric_service.purge_deleted(db) == 1
    remaining = db.scalars(select(BiometricTemplate.employee_id)).all()
    assert remaining == [setup["maria"]]


def test_daily_maintenance_purges_templates_and_old_identifications(
    client: TestClient, setup, auth_headers, db: Session
) -> None:
    identify(client, setup["kiosk"], b"FACE:maria#camera")
    client.delete(f"/api/v1/employees/{setup['joao']}/biometric-templates", headers=auth_headers)

    clock.freeze(local(1, "08:00") + timedelta(days=2))
    first = maintenance_service.run(db)
    assert (first.biometric_templates, first.kiosk_identifications) == (0, 0)

    clock.freeze(local(1, "08:00") + timedelta(days=31))
    second = maintenance_service.run(db)
    assert (second.biometric_templates, second.kiosk_identifications) == (1, 1)
    assert db.scalars(select(KioskIdentification)).all() == []
    assert db.scalars(select(BiometricTemplate.employee_id)).all() == [setup["maria"]]
    assert (
        db.scalar(select(AuditLog).where(AuditLog.action == "system.maintenance").limit(1))
        is not None
    )


def test_template_from_another_key_is_ignored_not_an_internal_error(
    client: TestClient, setup, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso real: o .env foi recriado com outra BIOMETRIC_KEY; os rostos antigos ficam ilegíveis."""
    import base64

    from app.core.config import get_settings

    other_key = base64.b64encode(b"k" * 32).decode()
    monkeypatch.setattr(get_settings(), "biometric_key", other_key)

    # Ninguém consegue ser lido: o terminal responde "não reconhecido", não erro interno.
    response = identify(client, setup["kiosk"], b"FACE:joao#camera")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FACE_NOT_RECOGNIZED"

    status = client.get(
        f"/api/v1/employees/{setup['joao']}/biometric-status", headers=auth_headers
    ).json()
    assert (status["templates"], status["unreadable_templates"], status["ready"]) == (0, 1, False)

    # Recadastrado com a chave atual, ele volta a ser reconhecido mesmo com a Maria ainda ilegível.
    client.delete(f"/api/v1/employees/{setup['joao']}/biometric-templates", headers=auth_headers)
    assert enroll(client, auth_headers, setup["joao"], "joao").status_code == 201
    again = identify(client, setup["kiosk"], b"FACE:joao#camera")
    assert again.status_code == 200, again.text
    assert again.json()["employee_name"] == "João"


def test_kiosk_hour_bank_shows_week_times_and_month_totals(
    client: TestClient, setup, db: Session
) -> None:
    """Pelo rosto: entrada, almoço e saída da semana e o total do mês até agora."""
    from tests.integration.helpers import full_day, punch

    full_day(db, setup["joao"], 1, "08:00", "12:00", "13:00", "17:00")  # terça 01/09
    punch(db, setup["joao"], "ENTRY", local(2, "08:05"))  # quarta 02/09, em andamento
    clock.freeze(local(2, "10:00"))

    token = identify(client, setup["kiosk"], b"FACE:joao#camera").json()["identification_token"]
    bank = client.post(
        f"{KIOSK}/hour-bank", json={"identification_token": token}, headers=setup["kiosk"]
    ).json()

    assert bank["week_start"] == "2026-08-31"  # segunda-feira
    week = {d["date"]: d for d in bank["week"]}
    assert list(week) == ["2026-08-31", "2026-09-01", "2026-09-02"]
    tuesday = week["2026-09-01"]
    assert tuesday["entry"] == "2026-09-01T08:00:00-03:00"
    assert tuesday["lunch_exit"] == "2026-09-01T12:00:00-03:00"
    assert tuesday["lunch_return"] == "2026-09-01T13:00:00-03:00"
    assert tuesday["exit"] == "2026-09-01T17:00:00-03:00"
    assert (tuesday["worked_minutes"], tuesday["planned_minutes"]) == (480, 480)
    assert week["2026-09-02"]["entry"] == "2026-09-02T08:05:00-03:00"
    assert week["2026-09-02"]["exit"] is None
    assert bank["week_worked_minutes"] == 480
    assert (bank["month_worked_minutes"], bank["month_balance_minutes"]) == (480, 0)
