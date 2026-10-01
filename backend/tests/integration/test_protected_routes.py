"""A08: toda rota administrativa exige administrador autenticado."""

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


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_requires_authentication(client: TestClient, method: str, path: str) -> None:
    url = re.sub(r"\{[^}]+\}", "1", path)
    response = client.request(method, url, json={})
    assert response.status_code == 401, f"{method} {path} respondeu {response.status_code}"
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
