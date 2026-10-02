"""Sequência e dia de jornada (BUSINESS-RULES.md §4; TEST-PLAN.md R01–R05, R13, R18)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.calculation.records import (
    Punch,
    allowed_next,
    is_valid_order,
    workday_for_new_entry,
)
from app.calculation.schedule import DaySchedule

TZ = ZoneInfo("America/Sao_Paulo")
WINDOW = timedelta(hours=4)


def p(t: str, hhmm: str, day: int = 1) -> Punch:
    h, m = map(int, hhmm.split(":"))
    return Punch(t, datetime(2026, 9, day, h, m, tzinfo=TZ))


def test_state_machine() -> None:
    assert allowed_next([]) == ("ENTRY",)
    assert allowed_next([p("ENTRY", "08:00")]) == ("LUNCH_EXIT", "EXIT")
    assert allowed_next([p("ENTRY", "08:00"), p("LUNCH_EXIT", "12:00")]) == ("LUNCH_RETURN",)
    assert allowed_next(
        [p("ENTRY", "08:00"), p("LUNCH_EXIT", "12:00"), p("LUNCH_RETURN", "13:00")]
    ) == ("EXIT",)
    assert allowed_next([p("ENTRY", "08:00"), p("EXIT", "17:00")]) == ()


def test_valid_order_for_adjustments() -> None:
    assert is_valid_order([p("ENTRY", "08:00"), p("EXIT", "17:00")])
    assert is_valid_order([p("EXIT", "17:00")])  # dia ainda sendo corrigido
    assert not is_valid_order([p("EXIT", "07:00"), p("ENTRY", "08:00")])
    assert not is_valid_order([p("ENTRY", "08:00"), p("LUNCH_RETURN", "13:00")])


def schedules(**by_weekday: tuple[str, str]):
    table = {
        int(k[1:]): DaySchedule(int(k[1:]), time.fromisoformat(a), time.fromisoformat(b), 0)
        for k, (a, b) in by_weekday.items()
    }
    return lambda d: table.get(d.weekday())


def test_entry_belongs_to_local_date_by_default() -> None:
    lookup = schedules(d3=("08:00", "17:00"))  # quinta
    assert workday_for_new_entry(p("ENTRY", "07:50", 10).at, lookup, TZ, WINDOW) == date(
        2026, 9, 10
    )


def test_r18_early_entry_for_next_day_shift() -> None:
    lookup = schedules(d4=("00:00", "08:00"))  # turno de sexta começa à meia-noite
    entry = p("ENTRY", "23:50", 10).at  # quinta 23:50
    assert workday_for_new_entry(entry, lookup, TZ, WINDOW) == date(2026, 9, 11)


def test_early_entry_does_not_steal_today_shift_still_running() -> None:
    lookup = schedules(d3=("16:00", "23:59"), d4=("00:00", "08:00"))
    entry = p("ENTRY", "23:00", 10).at  # ainda dentro do turno de quinta
    assert workday_for_new_entry(entry, lookup, TZ, WINDOW) == date(2026, 9, 10)
