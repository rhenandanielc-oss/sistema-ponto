import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import cli
from tests.conftest import ADMIN_PASSWORD, login


def answers(*values: str) -> Iterator[str]:
    return iter(values)


def test_create_admin_command(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    replies = answers("senha-do-terminal-1", "senha-do-terminal-1")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(replies))
    assert cli.main(["create-admin", "--email", "dono@empresa.com", "--name", "Dono"]) == 0
    assert login(client, "dono@empresa.com", "senha-do-terminal-1").status_code == 200


def test_create_admin_rejects_mismatch_and_short_password(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = answers("senha-do-terminal-1", "outra-senha-qualquer", "curta", "curta")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(replies))
    assert cli.main(["create-admin", "--email", "a@empresa.com", "--name", "A"]) == 1
    assert cli.main(["create-admin", "--email", "a@empresa.com", "--name", "A"]) == 1


def test_create_admin_with_password_from_stdin(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("senha-automatizada-1\n"))
    args = ["create-admin", "--email", "auto@empresa.com", "--name", "Auto", "--password-stdin"]
    assert cli.main(args) == 0
    assert login(client, "auto@empresa.com", "senha-automatizada-1").status_code == 200


def test_maintenance_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["maintenance"]) == 0
    assert "Manutenção concluída" in capsys.readouterr().out


def test_reset_password_unlocks_and_replaces_old_password(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, admin, capsys: pytest.CaptureFixture[str]
) -> None:
    for _ in range(5):
        login(client, "admin@empresa.com", "senha-errada-123")
    assert login(client, "admin@empresa.com", "senha-errada-123").status_code == 423  # bloqueado

    assert cli.main(["list-admins"]) == 0
    assert "admin@empresa.com" in capsys.readouterr().out

    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("nova-senha-segura-1\n"))
    args = ["reset-password", "--email", "ADMIN@empresa.com", "--password-stdin"]
    assert cli.main(args) == 0
    assert login(client, "admin@empresa.com", "nova-senha-segura-1").status_code == 200
    assert login(client, "admin@empresa.com", ADMIN_PASSWORD).status_code == 401


def test_reset_password_rejects_unknown_email_and_short_password(
    monkeypatch: pytest.MonkeyPatch, admin
) -> None:
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("nova-senha-segura-1\n"))
    assert cli.main(["reset-password", "--email", "x@x.com", "--password-stdin"]) == 1
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("curta\n"))
    assert cli.main(["reset-password", "--email", "admin@empresa.com", "--password-stdin"]) == 1
