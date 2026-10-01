"""Motor de cálculo — casos C01–C24 do TEST-PLAN.md (setembro de 2026, America/Sao_Paulo)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.calculation import workday as w
from app.calculation.records import Punch
from app.calculation.schedule import DaySchedule

TZ = ZoneInfo("America/Sao_Paulo")
RULES = w.Rules(tz=TZ)
LATER = datetime(2026, 12, 1, tzinfo=TZ)  # "agora" bem depois dos dias testados


def at(day: int, hhmm: str, month: int = 9) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, month, day, h, m, tzinfo=TZ)


def sched(
    start: str = "08:00", end: str = "17:00", lunch: int = 60, weekday: int = 0
) -> DaySchedule:
    return DaySchedule(weekday, time.fromisoformat(start), time.fromisoformat(end), lunch)


F1 = sched()  # 08:00–17:00, 60 min de almoço = 480


def punches(day: int, *times: str, next_day_from: int | None = None) -> tuple[Punch, ...]:
    """Batidas na ordem ENTRY, LUNCH_EXIT, LUNCH_RETURN, EXIT (ou ENTRY, EXIT se forem duas)."""
    types = (
        ("ENTRY", "EXIT") if len(times) == 2 else ("ENTRY", "LUNCH_EXIT", "LUNCH_RETURN", "EXIT")
    )
    result = []
    for i, (t, hhmm) in enumerate(zip(types, times, strict=False)):
        d = day + 1 if next_day_from is not None and i >= next_day_from else day
        result.append(Punch(t, at(d, hhmm)))
    return tuple(result)


def calc(
    day: int,
    p: tuple[Punch, ...] = (),
    schedule: DaySchedule | None = F1,
    holiday: bool = False,
    employed: bool = True,
    now: datetime = LATER,
) -> w.DayResult:
    inp = w.DayInput(date(2026, 9, day), schedule, employed=employed, holiday=holiday, punches=p)
    return w.calculate_day(inp, RULES, now)


def test_c01_c02_normal_day_and_normal_break() -> None:
    r = calc(1, punches(1, "08:00", "12:00", "13:00", "17:00"))
    assert (r.status, r.day_type) == (w.OK, w.WORKDAY)
    assert (r.planned_minutes, r.worked_minutes, r.break_minutes, r.balance_minutes) == (
        480,
        480,
        60,
        0,
    )
    assert r.flags == ()
    assert r.counts_for_bank


def test_c03_insufficient_break() -> None:
    r = calc(1, punches(1, "08:00", "12:00", "12:30", "17:00"))
    assert (r.worked_minutes, r.break_minutes, r.balance_minutes) == (510, 30, 30)
    assert w.INSUFFICIENT_BREAK in r.flags


def test_c04_late() -> None:
    r = calc(1, punches(1, "08:20", "12:00", "13:00", "17:00"))
    assert (r.late_minutes, r.worked_minutes, r.missing_minutes, r.balance_minutes) == (
        20,
        460,
        20,
        -20,
    )


def test_c05_within_tolerance() -> None:
    r = calc(1, punches(1, "08:04", "12:00", "13:00", "17:03"))
    assert r.worked_minutes == 479
    assert (r.late_minutes, r.balance_minutes, r.missing_minutes) == (0, 0, 0)


def test_c05b_long_lunch_is_not_forgiven_by_tolerance() -> None:
    r = calc(1, punches(1, "08:00", "12:00", "13:30", "17:00"))
    assert (r.worked_minutes, r.balance_minutes) == (450, -30)


def test_c05c_lunch_at_any_time() -> None:
    r = calc(1, punches(1, "08:00", "10:15", "11:15", "17:00"))
    assert (r.status, r.worked_minutes, r.balance_minutes) == (w.OK, 480, 0)


def test_c06_daily_tolerance_exceeded_counts_everything() -> None:
    r = calc(1, punches(1, "08:05", "12:00", "13:00", "16:54"))
    assert (r.late_minutes, r.early_leave_minutes, r.balance_minutes) == (5, 6, -11)


def test_c07_early_leave() -> None:
    r = calc(1, punches(1, "08:00", "12:00", "13:00", "16:00"))
    assert (r.early_leave_minutes, r.worked_minutes, r.balance_minutes) == (60, 420, -60)


def test_c08_overtime() -> None:
    r = calc(1, punches(1, "08:00", "12:00", "13:00", "18:30"))
    assert (r.worked_minutes, r.overtime_minutes, r.balance_minutes) == (570, 90, 90)


def test_c09_absence() -> None:
    r = calc(2)
    assert (r.status, r.worked_minutes, r.balance_minutes, r.missing_minutes) == (
        w.ABSENT,
        0,
        -480,
        480,
    )
    assert r.counts_for_bank


def test_c10_incomplete() -> None:
    r = calc(3, (*punches(3, "08:00", "12:00")[:1], Punch("LUNCH_EXIT", at(3, "12:00"))))
    assert (r.status, r.worked_minutes, r.counts_for_bank, r.balance_minutes) == (
        w.INCOMPLETE,
        240,
        False,
        0,
    )


def test_c11_different_schedule() -> None:
    r = calc(
        1, punches(1, "09:00", "12:00", "12:15", "15:15"), schedule=sched("09:00", "15:15", 15)
    )
    assert (r.planned_minutes, r.worked_minutes, r.break_minutes, r.balance_minutes) == (
        360,
        360,
        15,
        0,
    )


def test_c12_saturday_workday_absence() -> None:
    r = calc(5, schedule=sched("08:00", "12:00", 0, weekday=5))
    assert (r.status, r.balance_minutes) == (w.ABSENT, -240)


def test_c13_weekend_worked() -> None:
    r = calc(5, punches(5, "08:00", "12:00"), schedule=None)
    assert (r.day_type, r.planned_minutes, r.overtime_minutes, r.balance_minutes) == (
        w.DAY_OFF,
        0,
        240,
        240,
    )
    assert w.DAY_OFF_WORK in r.flags


def test_c14_weekend_off_is_not_absence() -> None:
    r = calc(6, schedule=None)
    assert (r.day_type, r.status, r.balance_minutes, r.counts_for_bank) == (
        w.DAY_OFF,
        w.NONE,
        0,
        False,
    )


def test_c15_holiday_off() -> None:
    r = calc(7, holiday=True)
    assert (r.day_type, r.planned_minutes, r.status, r.balance_minutes) == (w.HOLIDAY, 0, w.NONE, 0)


def test_c16_holiday_worked() -> None:
    r = calc(7, punches(7, "08:00", "12:00"), holiday=True)
    assert (r.overtime_minutes, r.balance_minutes) == (240, 240)
    assert w.HOLIDAY_WORK in r.flags


def test_c17_overnight_shift() -> None:
    p = punches(10, "22:00", "02:00", "03:00", "06:00", next_day_from=1)
    r = calc(10, p, schedule=sched("22:00", "06:00", 60, weekday=3))
    assert (r.status, r.planned_minutes, r.worked_minutes, r.balance_minutes) == (w.OK, 420, 420, 0)
    assert r.night_minutes == 360  # 22:00–02:00 + 03:00–05:00
    assert r.night_minutes_reduced == 411
    assert r.expected_end == at(11, "06:00")


def test_c18_schedule_change_is_applied_by_caller_per_day() -> None:
    before = calc(15, schedule=sched("08:00", "17:00"))
    after = calc(
        16, punches(16, "09:20", "12:00", "13:00", "16:00"), schedule=sched("09:00", "16:00")
    )
    assert before.planned_minutes == 480
    assert (after.planned_minutes, after.late_minutes) == (360, 20)


def test_c23_not_employed() -> None:
    r = calc(1, employed=False)
    assert (r.day_type, r.status, r.balance_minutes, r.counts_for_bank) == (
        w.NOT_EMPLOYED,
        w.NONE,
        0,
        False,
    )


def test_c24_open_shift_is_in_progress_then_incomplete() -> None:
    p = (Punch("ENTRY", at(1, "08:00")),)
    assert calc(1, p, now=at(1, "15:00")).status == w.IN_PROGRESS
    assert calc(1, p, now=at(2, "08:01")).status == w.INCOMPLETE


def test_today_without_punches_is_in_progress_until_shift_end() -> None:
    assert calc(1, now=at(1, "10:00")).status == w.IN_PROGRESS
    assert calc(1, now=at(1, "17:01")).status == w.ABSENT


def test_future_day() -> None:
    r = calc(30, now=at(1, "10:00"))
    assert (r.status, r.planned_minutes, r.counts_for_bank) == (w.FUTURE, 480, False)


def test_seconds_are_discarded() -> None:
    p = (
        Punch("ENTRY", at(1, "08:00") + timedelta(seconds=59)),
        Punch("EXIT", at(1, "12:00") + timedelta(seconds=30)),
    )
    r = calc(1, p, schedule=sched("08:00", "12:00", 0))
    assert r.worked_minutes == 239  # 3 h 59 min 31 s


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("08:00", "17:00", 0),
        ("20:00", "23:00", 60),
        ("04:00", "06:00", 60),
        ("21:00", "06:00", 420),
    ],
)
def test_night_minutes(start: str, end: str, expected: int) -> None:
    next_day = 1 if end < start else None
    p = punches(1, start, end, next_day_from=next_day)
    r = calc(1, p, schedule=None)
    assert r.night_minutes == expected
