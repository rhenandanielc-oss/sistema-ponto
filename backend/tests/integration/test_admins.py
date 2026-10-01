"""Gestão de administradores (TEST-PLAN.md §5, A10)."""

from fastapi.testclient import TestClient

from tests.conftest import login

ADMINS = "/api/v1/admins"


def test_create_list_and_update_admin(client: TestClient, auth_headers) -> None:
    created = client.post(
        ADMINS,
        json={"email": "Novo@Empresa.com", "name": " Novo ", "password": "outra-senha-123"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "novo@empresa.com"
    assert body["name"] == "Novo"
    assert "password" not in body and "password_hash" not in body

    assert login(client, "novo@empresa.com", "outra-senha-123").status_code == 200

    listing = client.get(ADMINS, headers=auth_headers).json()
    assert listing["total"] == 2

    updated = client.patch(
        f"{ADMINS}/{body['id']}", json={"password": "trocada-senha-1"}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert login(client, "novo@empresa.com", "outra-senha-123").status_code == 401
    assert login(client, "novo@empresa.com", "trocada-senha-1").status_code == 200


def test_duplicate_email_conflict(client: TestClient, auth_headers) -> None:
    response = client.post(
        ADMINS,
        json={"email": "ADMIN@empresa.com", "name": "Dup", "password": "outra-senha-123"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_short_password_rejected(client: TestClient, auth_headers) -> None:
    response = client.post(
        ADMINS,
        json={"email": "x@empresa.com", "name": "X", "password": "curta"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a10_cannot_deactivate_self_or_last_active_admin(
    client: TestClient, admin, auth_headers
) -> None:
    self_deactivation = client.post(f"{ADMINS}/{admin.id}/deactivate", headers=auth_headers)
    assert self_deactivation.status_code == 409

    other = client.post(
        ADMINS,
        json={"email": "b@empresa.com", "name": "B", "password": "outra-senha-123"},
        headers=auth_headers,
    ).json()
    other_headers = {
        "Authorization": "Bearer "
        + login(client, "b@empresa.com", "outra-senha-123").json()["access_token"]
    }
    # B desativa A (permitido: continua havendo um ativo)...
    assert client.post(f"{ADMINS}/{admin.id}/deactivate", headers=other_headers).status_code == 200
    # ...mas B não pode desativar a si mesmo, que agora é o último ativo.
    assert (
        client.post(f"{ADMINS}/{other['id']}/deactivate", headers=other_headers).status_code == 409
    )


def test_reactivate_admin(client: TestClient, admin, auth_headers) -> None:
    other = client.post(
        ADMINS,
        json={"email": "c@empresa.com", "name": "C", "password": "outra-senha-123"},
        headers=auth_headers,
    ).json()
    client.post(f"{ADMINS}/{other['id']}/deactivate", headers=auth_headers)
    response = client.post(f"{ADMINS}/{other['id']}/activate", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_unknown_admin_404(client: TestClient, auth_headers) -> None:
    response = client.patch(f"{ADMINS}/999", json={"name": "X"}, headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
