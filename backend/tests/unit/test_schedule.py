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


def day(
    start: str, end: str, lunch: tuple[str, str] | None = None, weekday: int = 0
) -> DaySchedule:
    t = time.fromisoformat
    return DaySchedule(
        weekday=weekday,
        start_time=t(start),
        end_time=t(end),
        lunch_start=t(lunch[0]) if lunch else None,
        lunch_end=t(lunch[1]) if lunch else None,
    )


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        (day("08:00", "17:00", ("12:00", "13:00")), 480),  # jornada padrão
        (day("09:00", "15:15", ("12:00", "12:15")), 360),  # intervalo de 15 min
        (day("08:00", "12:00"), 240),  # sem almoço
        (day("22:00", "06:00", ("02:00", "03:00")), 420),  # atravessa a meia-noite
        (day("19:00", "07:00", ("23:00", "00:00")), 660),  # almoço termina à meia-noite
        (day("00:00", "08:00"), 480),  # começa à meia-noite
    ],
)
def test_planned_minutes(schedule: DaySchedule, expected: int) -> None:
    assert planned_minutes(schedule) == expected


def test_overnight_offsets_are_continuous() -> None:
    offsets = shift_offsets(day("22:00", "06:00", ("02:00", "03:00")))
    assert (offsets.start, offsets.lunch_start, offsets.lunch_end, offsets.end) == (
        22 * 60,
        26 * 60,
        27 * 60,
        30 * 60,
    )


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (day("08:00", "17:00", ("13:00", "12:00")), "almoço"),  # retorno antes da saída
        (day("08:00", "17:00", ("07:00", "08:30")), "almoço"),  # almoço antes da entrada
        (day("08:00", "12:00", ("11:00", "13:00")), "almoço"),  # almoço depois da saída
        (day("08:00", "17:00", ("08:00", "09:00")), "almoço"),  # almoço junto com a entrada
        (day("06:00", "23:00"), "16 horas"),  # turno longo demais
        (day("08:00", "08:00"), "16 horas"),  # entrada igual à saída = 24 h
    ],
)
def test_invalid_day(schedule: DaySchedule, message: str) -> None:
    with pytest.raises(ScheduleError, match=message):
        shift_offsets(schedule)


def test_lunch_requires_both_times() -> None:
    with pytest.raises(ScheduleError, match="almoço"):
        shift_offsets(
            DaySchedule(weekday=0, start_time=time(8), end_time=time(17), lunch_start=time(12))
        )


def test_seconds_are_rejected() -> None:
    with pytest.raises(ScheduleError, match="segundos"):
        shift_offsets(day("08:00:30", "17:00"))


def test_week_requires_days_without_repetition() -> None:
    with pytest.raises(ScheduleError, match="pelo menos um dia"):
        validate_week([])
    with pytest.raises(ScheduleError, match="uma vez"):
        validate_week([day("08:00", "12:00", weekday=1), day("13:00", "17:00", weekday=1)])
    validate_week([day("08:00", "17:00", ("12:00", "13:00"), weekday=w) for w in range(5)])
