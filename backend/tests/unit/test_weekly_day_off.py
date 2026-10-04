"""Folga semanal em qualquer dia (BUSINESS-RULES.md §3.2)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.calculation.records import Punch
from app.calculation.schedule import DaySchedule
from app.calculation.weekly_day_off import WEEKLY_DAY_OFF, calculate_days
from app.calculation.workday import ABSENT, DAY_OFF_WORK, NONE, OK, DayInput, Rules

TZ = ZoneInfo("America/Sao_Paulo")
RULES = Rules(tz=TZ)
MONDAY = date(2026, 9, 7)  # segunda-feira
NOW = datetime(2026, 9, 30, 12, tzinfo=TZ)  # semanas avaliadas já terminaram


def at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(hhmm), TZ)


def worked(day: date) -> tuple[Punch, ...]:
    return (Punch("ENTRY", at(day, "08:00")), Punch("EXIT", at(day, "16:00")))


def week(off: set[int], holidays: frozenset[int] = frozenset(), start: date = MONDAY):
    """7 dias de trabalho 08:00–16:00 sem almoço (8 h); `off` = dias (0–6) sem batida."""
    days = [start + timedelta(days=i) for i in range(7)]
    return [
        DayInput(
            day=d,
            schedule=DaySchedule(d.weekday(), time(8), time(16), 0),
            employed=True,
            holiday=i in holidays,
            punches=() if i in off else worked(d),
        )
        for i, d in enumerate(days)
    ]


def run(inputs, now=NOW):
    holiday_days = {i.day for i in inputs if i.holiday}
    return calculate_days(
        inputs,
        RULES,
        now,
        rotating=lambda d: True,
        is_candidate_day=lambda d: d not in holiday_days,
    )


def summary(results):
    return [
        (r.status, r.planned_minutes, r.balance_minutes, WEEKLY_DAY_OFF in r.flags) for r in results
    ]


def test_day_off_on_thursday_is_not_an_absence() -> None:
    results = run(week(off={3}))
    assert summary(results)[3] == (NONE, 0, 0, True)
    assert all(r.status == OK and r.balance_minutes == 0 for i, r in enumerate(results) if i != 3)
    assert sum(r.planned_minutes for r in results) == 6 * 480


def test_day_off_on_sunday_is_not_an_absence() -> None:
    results = run(week(off={6}))
    assert summary(results)[6] == (NONE, 0, 0, True)
    assert sum(r.balance_minutes for r in results) == 0


def test_second_missing_day_is_an_absence() -> None:
    results = run(week(off={1, 4}))
    assert summary(results)[1] == (NONE, 0, 0, True)
    assert results[4].status == ABSENT and results[4].balance_minutes == -480


def test_working_all_seven_days_makes_the_last_one_overtime() -> None:
    results = run(week(off=set()))
    sunday = results[6]
    assert (sunday.planned_minutes, sunday.overtime_minutes) == (0, 480)
    assert DAY_OFF_WORK in sunday.flags and WEEKLY_DAY_OFF in sunday.flags
    assert sum(r.balance_minutes for r in results) == 480


def test_each_week_has_its_own_day_off() -> None:
    two_weeks = week(off={3}) + week(off={6}, start=MONDAY + timedelta(days=7))
    results = run(two_weeks)
    assert [r.day.weekday() for r in results if WEEKLY_DAY_OFF in r.flags] == [3, 6]
    assert sum(r.balance_minutes for r in results) == 0


def test_holiday_does_not_count_as_the_weekly_day_off() -> None:
    results = run(week(off={2, 4}, holidays=frozenset({2})))
    assert WEEKLY_DAY_OFF not in results[2].flags  # feriado
    assert summary(results)[4] == (NONE, 0, 0, True)


def test_current_week_before_the_last_day_keeps_planned_hours() -> None:
    wednesday_noon = at(MONDAY + timedelta(days=2), "12:00")
    results = run(week(off={2, 3, 4, 5, 6}), now=wednesday_noon)
    assert all(WEEKLY_DAY_OFF not in r.flags for r in results[:6])
    assert WEEKLY_DAY_OFF in results[6].flags  # domingo previsto como folga
    assert sum(r.planned_minutes for r in results) == 6 * 480


def test_without_the_option_nothing_changes() -> None:
    results = calculate_days(
        week(off={3}), RULES, NOW, rotating=lambda d: False, is_candidate_day=lambda d: False
    )
    assert results[3].status == ABSENT
    assert all(WEEKLY_DAY_OFF not in r.flags for r in results)
