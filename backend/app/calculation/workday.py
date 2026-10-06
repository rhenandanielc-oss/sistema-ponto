"""Motor de cálculo de um dia de jornada (BUSINESS-RULES.md §5–§7).

Função pura: recebe horário, batidas, feriado/contrato e o "agora"; devolve o resultado do dia.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.calculation.records import ENTRY, EXIT, LUNCH_EXIT, LUNCH_RETURN, Punch, shift_bounds
from app.calculation.schedule import DaySchedule, planned_minutes

WORKDAY = "WORKDAY"
DAY_OFF = "DAY_OFF"
HOLIDAY = "HOLIDAY"
NOT_EMPLOYED = "NOT_EMPLOYED"
BEFORE_TRACKING = (
    "BEFORE_TRACKING"  # antes do início do uso do sistema: não entra em nenhum cálculo
)

OK = "OK"
ABSENT = "ABSENT"
INCOMPLETE = "INCOMPLETE"
IN_PROGRESS = "IN_PROGRESS"
FUTURE = "FUTURE"
NONE = "NONE"

INSUFFICIENT_BREAK = "INSUFFICIENT_BREAK"
HOLIDAY_WORK = "HOLIDAY_WORK"
DAY_OFF_WORK = "DAY_OFF_WORK"

NIGHT_HOUR_MINUTES = 52.5  # hora noturna reduzida (CLT art. 73)


@dataclass(frozen=True)
class Rules:
    tz: ZoneInfo
    tolerance_per_mark_minutes: int = 5
    tolerance_daily_minutes: int = 10
    max_shift: timedelta = timedelta(hours=16)
    night_start: time = time(22)
    night_end: time = time(5)


@dataclass(frozen=True)
class DayInput:
    day: date
    schedule: DaySchedule | None  # None = dia não trabalhado no horário do funcionário
    employed: bool
    holiday: bool
    punches: tuple[Punch, ...] = ()
    tracked: bool = True  # False = antes do início do controle de ponto (configuração da empresa)


@dataclass(frozen=True)
class DayResult:
    day: date
    day_type: str
    status: str
    flags: tuple[str, ...] = ()
    planned_minutes: int = 0
    worked_minutes: int = 0
    break_minutes: int = 0
    late_minutes: int = 0
    early_leave_minutes: int = 0
    missing_minutes: int = 0
    overtime_minutes: int = 0
    night_minutes: int = 0
    night_minutes_reduced: int = 0
    balance_minutes: int = 0
    counts_for_bank: bool = False
    expected_start: datetime | None = None
    expected_end: datetime | None = None
    punches: tuple[Punch, ...] = field(default=())


def _minutes(delta: timedelta) -> int:
    """Minutos inteiros (segundos desprezados)."""
    return int(delta.total_seconds() // 60)


def _day_type(inp: DayInput) -> str:
    if not inp.employed:
        return NOT_EMPLOYED
    if not inp.tracked:
        return BEFORE_TRACKING
    if inp.holiday:
        return HOLIDAY
    if inp.schedule is None:
        return DAY_OFF
    return WORKDAY


def _night_minutes(intervals: list[tuple[datetime, datetime]], rules: Rules) -> int:
    total = timedelta(0)
    for start, end in intervals:
        first = start.astimezone(rules.tz).date() - timedelta(days=1)
        last = end.astimezone(rules.tz).date()
        d = first
        while d <= last:
            window_start = datetime.combine(d, rules.night_start, rules.tz)
            end_day = d + timedelta(days=1) if rules.night_end <= rules.night_start else d
            window_end = datetime.combine(end_day, rules.night_end, rules.tz)
            overlap = min(end, window_end) - max(start, window_start)
            if overlap > timedelta(0):
                total += overlap
            d += timedelta(days=1)
    return _minutes(total)


def calculate_day(inp: DayInput, rules: Rules, now: datetime) -> DayResult:
    day_type = _day_type(inp)
    planned = planned_minutes(inp.schedule) if day_type == WORKDAY and inp.schedule else 0
    expected_start = expected_end = None
    if day_type == WORKDAY and inp.schedule is not None:
        expected_start, expected_end = shift_bounds(inp.day, inp.schedule, rules.tz)

    base = DayResult(
        day=inp.day,
        day_type=day_type,
        status=NONE,
        planned_minutes=planned,
        expected_start=expected_start,
        expected_end=expected_end,
        punches=tuple(sorted(inp.punches, key=lambda p: p.at)),
    )
    if day_type == BEFORE_TRACKING:
        return base  # sem horas previstas, faltas ou extras: o sistema ainda não era usado
    by_type = {p.type: p.at for p in inp.punches}
    today = now.astimezone(rules.tz).date()

    # Sem batidas.
    if not inp.punches:
        if day_type != WORKDAY:
            return replace(base, status=FUTURE if inp.day > today else NONE)
        assert expected_end is not None
        if now < expected_end:
            return replace(base, status=FUTURE if inp.day > today else IN_PROGRESS)
        return replace(
            base,
            status=ABSENT,
            missing_minutes=planned,
            balance_minutes=-planned,
            counts_for_bank=True,
        )

    # Períodos fechados.
    intervals: list[tuple[datetime, datetime]] = []
    entry, exit_ = by_type.get(ENTRY), by_type.get(EXIT)
    lunch_out, lunch_back = by_type.get(LUNCH_EXIT), by_type.get(LUNCH_RETURN)
    if entry and lunch_out:
        intervals.append((entry, lunch_out))
    if lunch_back and exit_:
        intervals.append((lunch_back, exit_))
    if entry and exit_ and not lunch_out and not lunch_back:
        intervals.append((entry, exit_))
    worked = sum(_minutes(b - a) for a, b in intervals)
    night = _night_minutes(intervals, rules)
    night_reduced = round(night * 60 / NIGHT_HOUR_MINUTES)

    complete = (
        entry is not None and exit_ is not None and (lunch_out is None) == (lunch_back is None)
    )
    if not complete:
        open_shift = entry is not None and exit_ is None and now - entry <= rules.max_shift
        return replace(
            base,
            status=IN_PROGRESS if open_shift else INCOMPLETE,
            worked_minutes=worked,
            night_minutes=night,
            night_minutes_reduced=night_reduced,
        )
    assert entry is not None and exit_ is not None

    break_minutes = _minutes(lunch_back - lunch_out) if lunch_out and lunch_back else 0
    flags: list[str] = []
    if (worked > 360 and break_minutes < 60) or (240 < worked <= 360 and break_minutes < 15):
        flags.append(INSUFFICIENT_BREAK)

    late = early = 0
    if day_type == WORKDAY:
        assert expected_start is not None and expected_end is not None
        balance = worked - planned
        late = max(0, _minutes(entry - expected_start))
        early = max(0, _minutes(expected_end - exit_))
        deviation_in = _minutes(abs(entry - expected_start))
        deviation_out = _minutes(abs(exit_ - expected_end))
        within_tolerance = (
            deviation_in <= rules.tolerance_per_mark_minutes
            and deviation_out <= rules.tolerance_per_mark_minutes
            and deviation_in + deviation_out <= rules.tolerance_daily_minutes
            and abs(balance) <= rules.tolerance_daily_minutes
        )
        if within_tolerance:
            balance = late = early = 0
    else:
        # Folga, feriado (ou fora do contrato): todo tempo trabalhado é hora extra.
        balance = worked
        flags.append(HOLIDAY_WORK if day_type == HOLIDAY else DAY_OFF_WORK)

    return replace(
        base,
        status=OK,
        flags=tuple(flags),
        worked_minutes=worked,
        break_minutes=break_minutes,
        late_minutes=late,
        early_leave_minutes=early,
        missing_minutes=max(0, -balance),
        overtime_minutes=max(0, balance),
        night_minutes=night,
        night_minutes_reduced=night_reduced,
        balance_minutes=balance,
        counts_for_bank=True,
    )
