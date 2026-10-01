from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from app.models import TimeRecord
from app.services import audit, record_service

TZ = ZoneInfo("America/Sao_Paulo")
KIOSK = audit.Actor("DEVICE")


def local(day: int, hhmm: str, month: int = 9, second: int = 0) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, month, day, h, m, second, tzinfo=TZ)


def create_employee(
    client: TestClient,
    headers: dict[str, str],
    *,
    registration: str = "001",
    name: str = "João",
    hire_date: str = "2026-09-01",
    schedule: dict[str, Any] | None = None,
) -> int:
    response = client.post(
        "/api/v1/employees",
        json={
            "name": name,
            "registration_number": registration,
            "hire_date": hire_date,
            "schedule": schedule or {"start_time": "08:00", "end_time": "17:00"},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def punch(db: Session, employee_id: int, record_type: str, at: datetime) -> TimeRecord:
    """Simula a batida do kiosk no instante `at` (relógio do servidor congelado)."""
    clock.freeze(at)
    return record_service.create_record(
        db, employee_id=employee_id, record_type=record_type, actor=KIOSK
    )


def full_day(db: Session, employee_id: int, day: int, *times: str) -> None:
    types = (
        ("ENTRY", "EXIT") if len(times) == 2 else ("ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT")
    )
    for record_type, hhmm in zip(types, times, strict=True):
        punch(db, employee_id, record_type, local(day, hhmm))
