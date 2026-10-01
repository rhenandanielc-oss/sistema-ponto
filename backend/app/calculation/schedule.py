"""Regras puras do horário fixo do funcionário (BUSINESS-RULES.md §3).

O horário fixo é só entrada e saída (ex.: 08:00 - 16:00). O almoço é livre: o funcionário escolhe
quando sair e voltar; o horário guarda apenas a duração prevista do almoço, descontada da carga.

Sem acesso a banco ou relógio: recebe horários e devolve minutos ou erros de validação.
"""

from dataclasses import dataclass
from datetime import time

MINUTES_PER_DAY = 24 * 60
MAX_SHIFT_MINUTES = 16 * 60
DEFAULT_LUNCH_MINUTES = 60

WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True)
class DaySchedule:
    weekday: int
    start_time: time
    end_time: time
    lunch_minutes: int = DEFAULT_LUNCH_MINUTES


@dataclass(frozen=True)
class ShiftOffsets:
    """Entrada e saída em minutos a partir da meia-noite do início (saída pode passar de 1440)."""

    start: int
    end: int
    lunch_minutes: int

    @property
    def planned_minutes(self) -> int:
        return self.end - self.start - self.lunch_minutes


class ScheduleError(ValueError):
    pass


def _minutes(t: time) -> int:
    if t.second or t.microsecond:
        raise ScheduleError("Horários devem ser informados em horas e minutos (sem segundos).")
    return t.hour * 60 + t.minute


def shift_offsets(day: DaySchedule) -> ShiftOffsets:
    """Valida o horário de um dia e o converte em minutos contínuos a partir da entrada."""
    if not 0 <= day.weekday <= 6:
        raise ScheduleError(f"Dia da semana inválido: {day.weekday}.")
    name = WEEKDAY_NAMES[day.weekday]

    start = _minutes(day.start_time)
    end = _minutes(day.end_time)
    end = end + MINUTES_PER_DAY if end <= start else end  # saída no dia seguinte (turno noturno)
    if end - start > MAX_SHIFT_MINUTES:
        raise ScheduleError(f"{name}: o turno não pode passar de 16 horas.")
    if day.lunch_minutes < 0:
        raise ScheduleError(f"{name}: a duração do almoço não pode ser negativa.")
    if day.lunch_minutes >= end - start:
        raise ScheduleError(f"{name}: o almoço deve ser menor que o turno.")
    return ShiftOffsets(start=start, end=end, lunch_minutes=day.lunch_minutes)


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
