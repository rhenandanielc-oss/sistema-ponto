"""Batidas de ponto — TEST-PLAN.md R01–R18 contra o PostgreSQL real."""

import threading
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError
from app.db.session import get_sessionmaker
from app.models import AuditLog, TimeRecord
from app.services import record_service
from tests.integration.helpers import KIOSK, create_employee, full_day, local, punch


def error_code(exc: pytest.ExceptionInfo[AppError]) -> str:
    return exc.value.code


@pytest.fixture
def employee(client: TestClient, auth_headers) -> int:
    return create_employee(client, auth_headers)


def test_r01_full_sequence_uses_server_time(db: Session, employee: int) -> None:
    full_day(db, employee, 1, "08:00", "12:00", "13:00", "17:00")
    records = db.scalars(select(TimeRecord).order_by(TimeRecord.id)).all()
    assert [r.type for r in records] == ["ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT"]
    assert records[0].recorded_at == local(1, "08:00")
    assert {r.workday_date for r in records} == {date(2026, 9, 1)}
    assert {r.source for r in records} == {"KIOSK"}


def test_r02_without_lunch(db: Session, employee: int) -> None:
    full_day(db, employee, 1, "08:00", "17:00")
    assert db.scalar(select(func.count()).select_from(TimeRecord)) == 2


def test_r03_first_record_must_be_entry(db: Session, employee: int) -> None:
    with pytest.raises(AppError) as exc:
        punch(db, employee, "EXIT", local(1, "17:00"))
    assert error_code(exc) == "INVALID_SEQUENCE"
    assert exc.value.details == {"expected": ["ENTRY"]}


def test_r04_return_without_lunch_exit(db: Session, employee: int) -> None:
    punch(db, employee, "ENTRY", local(1, "08:00"))
    with pytest.raises(AppError) as exc:
        punch(db, employee, "LUNCH_RETURN", local(1, "13:00"))
    assert error_code(exc) == "INVALID_SEQUENCE"


def test_r05_nothing_after_exit_on_same_workday(db: Session, employee: int) -> None:
    full_day(db, employee, 1, "08:00", "17:00")
    with pytest.raises(AppError) as exc:
        punch(db, employee, "LUNCH_EXIT", local(1, "18:00"))
    assert error_code(exc) == "INVALID_SEQUENCE"


def test_r06_duplicate_type_is_rejected_and_audited(db: Session, employee: int) -> None:
    punch(db, employee, "ENTRY", local(1, "08:00"))
    with pytest.raises(AppError) as exc:
        punch(db, employee, "ENTRY", local(1, "09:00"))
    assert error_code(exc) == "DUPLICATE_RECORD"
    rejected = db.scalars(select(AuditLog).where(AuditLog.action == "record.rejected")).all()
    assert [r.after for r in rejected] == [{"type": "ENTRY", "code": "DUPLICATE_RECORD"}]


def test_r07_records_less_than_two_minutes_apart(db: Session, employee: int) -> None:
    punch(db, employee, "ENTRY", local(1, "08:00"))
    with pytest.raises(AppError) as exc:
        punch(db, employee, "EXIT", local(1, "08:01", second=30))
    assert error_code(exc) == "DUPLICATE_RECORD"
    punch(db, employee, "EXIT", local(1, "08:02"))  # 2 minutos depois é aceito


def test_r08_concurrent_entries_create_a_single_record(employee: int) -> None:
    clock.freeze(local(1, "08:00"))
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        with get_sessionmaker()() as session:
            barrier.wait()
            try:
                record_service.create_record(
                    session, employee_id=employee, record_type="ENTRY", actor=KIOSK
                )
                results.append("created")
            except AppError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["DUPLICATE_RECORD", "created"]
    with get_sessionmaker()() as session:
        assert session.scalar(select(func.count()).select_from(TimeRecord)) == 1


def test_r09_inactive_employee(
    client: TestClient, auth_headers, db: Session, employee: int
) -> None:
    client.post(f"/api/v1/employees/{employee}/deactivate", headers=auth_headers)
    with pytest.raises(AppError) as exc:
        punch(db, employee, "ENTRY", local(1, "08:00"))
    assert error_code(exc) == "EMPLOYEE_INACTIVE"


def test_r09b_before_hire_date(db: Session, employee: int) -> None:
    with pytest.raises(AppError) as exc:
        punch(db, employee, "ENTRY", local(31, "08:00", month=8))
    assert error_code(exc) == "EMPLOYEE_INACTIVE"


def test_r10_unknown_employee_is_audited(db: Session) -> None:
    with pytest.raises(AppError) as exc:
        punch(db, 999, "ENTRY", local(1, "08:00"))
    assert error_code(exc) == "EMPLOYEE_NOT_FOUND"
    assert db.scalar(select(AuditLog.action).where(AuditLog.action == "record.rejected"))


def test_r12_server_time_is_the_only_time(db: Session, employee: int) -> None:
    record = punch(db, employee, "ENTRY", local(1, "08:07", second=13))
    assert record.recorded_at == local(1, "08:07", second=13)


def test_r13_overnight_exit_belongs_to_entry_day(
    client: TestClient, auth_headers, db: Session
) -> None:
    night = create_employee(
        client,
        auth_headers,
        registration="N1",
        schedule={"start_time": "22:00", "end_time": "06:00"},
    )
    punch(db, night, "ENTRY", local(10, "22:00"))
    punch(db, night, "LUNCH_EXIT", local(11, "02:00"))
    punch(db, night, "LUNCH_RETURN", local(11, "03:00"))
    record = punch(db, night, "EXIT", local(11, "06:00"))
    assert record.workday_date == date(2026, 9, 10)


def test_r14_open_cycle_older_than_16h_does_not_absorb_new_records(
    db: Session, employee: int
) -> None:
    punch(db, employee, "ENTRY", local(1, "08:00"))  # esqueceu a saída
    record = punch(db, employee, "ENTRY", local(2, "08:00"))
    assert record.workday_date == date(2026, 9, 2)
    with pytest.raises(AppError) as exc:
        punch(db, employee, "ENTRY", local(2, "08:05"))
    assert error_code(exc) == "DUPLICATE_RECORD"


def test_r18_early_entry_for_midnight_shift(client: TestClient, auth_headers, db: Session) -> None:
    worker = create_employee(
        client,
        auth_headers,
        registration="N2",
        schedule={"start_time": "00:00", "end_time": "08:00", "lunch_minutes": 0, "weekdays": [4]},
    )
    record = punch(db, worker, "ENTRY", local(10, "23:50"))  # quinta 23:50, turno de sexta
    assert record.workday_date == date(2026, 9, 11)


def test_allowed_types_for_kiosk_buttons(db: Session, employee: int) -> None:
    clock.freeze(local(1, "07:55"))
    assert record_service.allowed_types(db, employee) == (date(2026, 9, 1), ("ENTRY",))
    punch(db, employee, "ENTRY", local(1, "08:00"))
    clock.freeze(local(1, "11:00"))
    assert record_service.allowed_types(db, employee)[1] == ("LUNCH_EXIT", "EXIT")


def test_r11_without_schedule(db: Session, employee: int) -> None:
    """Não acontece pela API (o cadastro exige horário); defesa caso o banco seja alterado."""
    db.execute(text("DELETE FROM employee_schedules"))
    db.commit()
    with pytest.raises(AppError) as exc:
        punch(db, employee, "ENTRY", local(1, "08:00"))
    assert error_code(exc) == "NO_APPLICABLE_SCHEDULE"
