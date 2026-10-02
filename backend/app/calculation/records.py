"""Regras puras das batidas: sequência e dia de jornada (BUSINESS-RULES.md §4)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.calculation.schedule import DaySchedule, shift_offsets

ENTRY = "ENTRY"
LUNCH_EXIT = "LUNCH_EXIT"
LUNCH_RETURN = "LUNCH_RETURN"
EXIT = "EXIT"
ORDER = (ENTRY, LUNCH_EXIT, LUNCH_RETURN, EXIT)

# Estado (último tipo batido no dia) -> próximos tipos permitidos.
_NEXT: dict[str | None, tuple[str, ...]] = {
    None: (ENTRY,),
    ENTRY: (LUNCH_EXIT, EXIT),
    LUNCH_EXIT: (LUNCH_RETURN,),
    LUNCH_RETURN: (EXIT,),
    EXIT: (),
}


@dataclass(frozen=True)
class Punch:
    type: str
    at: datetime  # sempre com fuso


def allowed_next(punches: Iterable[Punch]) -> tuple[str, ...]:
    """Tipos que podem ser batidos agora, dado o que já existe no dia de jornada."""
    ordered = sorted(punches, key=lambda p: p.at)
    return _NEXT[ordered[-1].type if ordered else None]


def is_valid_order(punches: Iterable[Punch]) -> bool:
    """Batidas de um dia, ordenadas pelo horário, seguem ENTRY < LUNCH_EXIT < LUNCH_RETURN < EXIT.

    Aceita dias ainda incompletos (usado nos ajustes do administrador, que podem preencher lacunas).
    """
    ordered = sorted(punches, key=lambda p: p.at)
    positions = [ORDER.index(p.type) for p in ordered]
    if positions != sorted(set(positions)):
        return False
    types = {p.type for p in ordered}
    return not (LUNCH_RETURN in types and LUNCH_EXIT not in types)


def shift_bounds(day: date, schedule: DaySchedule, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Entrada e saída previstas de um dia, como instantes com fuso."""
    offsets = shift_offsets(schedule)
    midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
    return (
        _local(midnight, offsets.start, tz),
        _local(midnight, offsets.end, tz),
    )


def _local(midnight: datetime, minutes: int, tz: ZoneInfo) -> datetime:
    # Soma em horário de parede e reaplica o fuso: correto mesmo em dias com mudança de horário.
    naive = midnight.replace(tzinfo=None) + timedelta(minutes=minutes)
    return naive.replace(tzinfo=tz)


def workday_for_new_entry(
    at: datetime,
    schedule_for: Callable[[date], DaySchedule | None],
    tz: ZoneInfo,
    early_entry_window: timedelta,
) -> date:
    """Dia de jornada de uma ENTRY que não pertence a um turno aberto (BUSINESS-RULES.md §4.4).

    Regra: a data local da batida; exceto quando ela acontece pouco antes de um turno previsto
    para o dia seguinte (ex.: 23:50 para turno que começa 00:00) e o turno de hoje já terminou
    ou não existe.
    """
    local_day = at.astimezone(tz).date()
    tomorrow = local_day + timedelta(days=1)
    next_schedule = schedule_for(tomorrow)
    if next_schedule is not None:
        next_start, _ = shift_bounds(tomorrow, next_schedule, tz)
        if timedelta(0) <= next_start - at <= early_entry_window:
            today_schedule = schedule_for(local_day)
            if today_schedule is None or at >= shift_bounds(local_day, today_schedule, tz)[1]:
                return tomorrow
    return local_day
