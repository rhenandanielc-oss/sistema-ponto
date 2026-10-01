"""O banco recusa alterar ou apagar o histórico (migration 0006, SECURITY.md §8)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core import clock
from tests.integration.helpers import create_employee, local, punch

FORBIDDEN = [
    "UPDATE audit_logs SET action = 'x'",
    "DELETE FROM audit_logs",
    "UPDATE time_records SET recorded_at = recorded_at - interval '1 hour'",
    "UPDATE time_records SET type = 'EXIT'",
    "DELETE FROM time_records",
    "UPDATE time_record_adjustments SET reason = 'outro motivo qualquer'",
    "DELETE FROM time_record_adjustments",
    "UPDATE hour_bank_entries SET minutes = 999",
    "DELETE FROM hour_bank_entries",
]


@pytest.fixture
def history(client: TestClient, auth_headers, db: Session) -> int:
    employee = create_employee(client, auth_headers)
    record = punch(db, employee, "ENTRY", local(1, "08:00"))
    clock.freeze(local(2, "09:00"))
    voided = client.post(
        "/api/v1/time-records/adjustments",
        json={"kind": "VOID", "record_id": record.id, "reason": "Batida registrada por engano"},
        headers=auth_headers,
    )
    assert voided.status_code == 201, voided.text
    punch(db, employee, "ENTRY", local(2, "08:00"))
    entry = client.post(
        f"/api/v1/employees/{employee}/hour-bank/entries",
        json={
            "entry_date": "2026-09-02",
            "minutes": 60,
            "kind": "CORRECTION",
            "reason": "Acerto de saldo inicial",
        },
        headers=auth_headers,
    )
    assert entry.status_code == 201, entry.text
    return record.id


@pytest.mark.parametrize("statement", FORBIDDEN)
def test_history_cannot_be_changed(history: int, db: Session, statement: str) -> None:
    with pytest.raises(DBAPIError, match="imutáve"):
        db.execute(text(statement))
    db.rollback()


def test_voided_record_cannot_be_unvoided(history: int, db: Session) -> None:
    with pytest.raises(DBAPIError, match="imutáve"):
        db.execute(
            text(
                "UPDATE time_records SET voided_at = NULL, voided_by_adjustment_id = NULL "
                "WHERE id = :id"
            ),
            {"id": history},
        )
    db.rollback()


def test_rows_survive(history: int, db: Session) -> None:
    for table in ("audit_logs", "time_records", "time_record_adjustments", "hour_bank_entries"):
        assert db.scalar(text(f"SELECT count(*) FROM {table}")) > 0
