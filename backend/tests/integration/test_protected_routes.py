"""A08/A09: rotas de administrador exigem administrador; as do kiosk, terminal autorizado."""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PUBLIC = {
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}

# Lista a partir do OpenAPI: cobre automaticamente toda rota nova.
ROUTES = [
    (method.upper(), path)
    for path, operations in create_app().openapi()["paths"].items()
    if path not in PUBLIC
    for method in sorted(operations)
]


def test_route_list_is_not_empty() -> None:
    assert len(ROUTES) > 10


ADMIN_ROUTES = [(m, p) for m, p in ROUTES if not p.startswith("/api/v1/kiosk/")]
KIOSK_ROUTES = [(m, p) for m, p in ROUTES if p.startswith("/api/v1/kiosk/")]


def url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_routes_require_admin(client: TestClient, method: str, path: str) -> None:
    for headers in ({}, {"Authorization": "Device qualquer-token"}):
        response = client.request(method, url(path), json={}, headers=headers)
        assert response.status_code == 401, f"{method} {path} respondeu {response.status_code}"
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(("method", "path"), KIOSK_ROUTES)
def test_kiosk_routes_require_device(
    client: TestClient, auth_headers: dict[str, str], method: str, path: str
) -> None:
    for headers in ({}, auth_headers, {"Authorization": "Device token-invalido"}):
        response = client.request(method, url(path), json={}, headers=headers)
        assert response.status_code == 403, f"{method} {path} respondeu {response.status_code}"
        assert response.json()["error"]["code"] == "DEVICE_NOT_AUTHORIZED"
