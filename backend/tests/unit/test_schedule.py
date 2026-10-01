"""Regras do horário fixo (BUSINESS-RULES.md §3; TEST-PLAN.md §6)."""

from datetime import time

import pytest

from app.calculation.schedule import (
    DaySchedule,
    ScheduleError,
    planned_minutes,
    shift_offsets,
    validate_week,
)


def day(start: str, end: str, lunch: int = 60, weekday: int = 0) -> DaySchedule:
    return DaySchedule(
        weekday=weekday,
        start_time=time.fromisoformat(start),
        end_time=time.fromisoformat(end),
        lunch_minutes=lunch,
    )


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        (day("08:00", "16:00"), 420),  # exemplo do João: 8 h de turno - 1 h de almoço
        (day("08:00", "17:00"), 480),
        (day("09:00", "15:15", lunch=15), 360),
        (day("08:00", "12:00", lunch=0), 240),  # sem almoço
        (day("22:00", "06:00"), 420),  # atravessa a meia-noite
        (day("00:00", "08:00", lunch=0), 480),  # começa à meia-noite
    ],
)
def test_planned_minutes(schedule: DaySchedule, expected: int) -> None:
    assert planned_minutes(schedule) == expected


def test_overnight_offsets_are_continuous() -> None:
    offsets = shift_offsets(day("22:00", "06:00"))
    assert (offsets.start, offsets.end) == (22 * 60, 30 * 60)


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (day("06:00", "23:00"), "16 horas"),  # turno longo demais
        (day("08:00", "08:00"), "16 horas"),  # entrada igual à saída = 24 h
        (day("08:00", "09:00", lunch=60), "almoço"),  # almoço do tamanho do turno
        (day("08:00", "16:00", lunch=-1), "negativa"),
    ],
)
def test_invalid_day(schedule: DaySchedule, message: str) -> None:
    with pytest.raises(ScheduleError, match=message):
        shift_offsets(schedule)


def test_seconds_are_rejected() -> None:
    with pytest.raises(ScheduleError, match="segundos"):
        shift_offsets(day("08:00:30", "17:00"))


def test_week_requires_days_without_repetition() -> None:
    with pytest.raises(ScheduleError, match="pelo menos um dia"):
        validate_week([])
    with pytest.raises(ScheduleError, match="uma vez"):
        validate_week([day("08:00", "12:00", weekday=1), day("13:00", "17:00", weekday=1)])
    validate_week([day("08:00", "17:00", weekday=w) for w in range(5)])
