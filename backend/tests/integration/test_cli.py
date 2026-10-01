import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import cli
from tests.conftest import login


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
