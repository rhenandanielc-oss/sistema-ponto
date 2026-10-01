"""Regras puras do horário fixo do funcionário (BUSINESS-RULES.md §3).

Sem acesso a banco ou relógio: recebe horários e devolve minutos ou erros de validação.
"""

from dataclasses import dataclass
from datetime import time

MINUTES_PER_DAY = 24 * 60
MAX_SHIFT_MINUTES = 16 * 60

WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True)
class DaySchedule:
    weekday: int
    start_time: time
    end_time: time
    lunch_start: time | None = None
    lunch_end: time | None = None


@dataclass(frozen=True)
class ShiftOffsets:
    """Minutos relativos à meia-noite do dia de início do turno (podem passar de 1440)."""

    start: int
    end: int
    lunch_start: int | None
    lunch_end: int | None

    @property
    def planned_minutes(self) -> int:
        lunch = (
            self.lunch_end - self.lunch_start
            if self.lunch_start is not None and self.lunch_end is not None
            else 0
        )
        return self.end - self.start - lunch


class ScheduleError(ValueError):
    pass


def _minutes(t: time) -> int:
    if t.second or t.microsecond:
        raise ScheduleError("Horários devem ser informados em horas e minutos (sem segundos).")
    return t.hour * 60 + t.minute


def _after(value: int, reference: int) -> int:
    """Desloca `value` para o dia seguinte se ele vier antes de `reference` (turno noturno)."""
    return value + MINUTES_PER_DAY if value < reference else value


def shift_offsets(day: DaySchedule) -> ShiftOffsets:
    """Valida o horário de um dia e o converte em minutos contínuos a partir do início do turno."""
    name = WEEKDAY_NAMES[day.weekday] if 0 <= day.weekday <= 6 else str(day.weekday)
    if not 0 <= day.weekday <= 6:
        raise ScheduleError(f"Dia da semana inválido: {day.weekday}.")
    if (day.lunch_start is None) != (day.lunch_end is None):
        raise ScheduleError(f"{name}: informe saída e retorno do almoço, ou nenhum dos dois.")

    start = _minutes(day.start_time)
    end = _minutes(day.end_time)
    end = end + MINUTES_PER_DAY if end <= start else end
    if end - start > MAX_SHIFT_MINUTES:
        raise ScheduleError(f"{name}: o turno não pode passar de 16 horas.")

    lunch_start = lunch_end = None
    if day.lunch_start is not None and day.lunch_end is not None:
        lunch_start = _after(_minutes(day.lunch_start), start)
        lunch_end = _after(_minutes(day.lunch_end), start)
        if not start < lunch_start < lunch_end < end:
            raise ScheduleError(
                f"{name}: o almoço deve começar depois da entrada e terminar antes da saída."
            )

    return ShiftOffsets(start=start, end=end, lunch_start=lunch_start, lunch_end=lunch_end)


def planned_minutes(day: DaySchedule) -> int:
    return shift_offsets(day).planned_minutes


def validate_week(days: list[DaySchedule]) -> None:
    if not days:
        raise ScheduleError("Informe pelo menos um dia trabalhado.")
    weekdays = [d.weekday for d in days]
    if len(set(weekdays)) != len(weekdays):
        raise ScheduleError("Cada dia da semana só pode aparecer uma vez.")
    for day in days:
        shift_offsets(day)
