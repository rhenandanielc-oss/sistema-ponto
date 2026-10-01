import os

# Configuração precisa existir antes de importar a aplicação.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://ponto:ponto@localhost:5432/ponto_test"
)
os.environ["COOKIE_SECURE"] = "false"
os.environ["JWT_SECRET"] = "test-only-jwt-key-0123456789abcdef0123456789"

from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import clock
from app.db.base import Base
from app.db.session import get_engine, get_sessionmaker
from app.main import create_app
from app.schemas.admin import AdminCreate
from app.services import admin_service, audit

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
ADMIN_PASSWORD = "senha-segura-123"


def alembic_config() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    clock.freeze(None)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def make_admin(db: Session, email: str = "admin@empresa.com", name: str = "Admin") -> Any:
    return admin_service.create(
        db, AdminCreate(email=email, name=name, password=ADMIN_PASSWORD), audit.SYSTEM
    )


@pytest.fixture
def admin(db: Session) -> Any:
    return make_admin(db)


def login(
    client: TestClient, email: str = "admin@empresa.com", password: str = ADMIN_PASSWORD
) -> Any:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def auth_headers(client: TestClient, admin: Any) -> dict[str, str]:
    response = login(client)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
