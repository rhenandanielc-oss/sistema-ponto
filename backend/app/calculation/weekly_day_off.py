"""Folga semanal em qualquer dia (BUSINESS-RULES.md §3.2).

Para funcionários com essa opção no horário, cada semana (segunda a domingo) tem uma folga:
* é o **primeiro dia de trabalho sem batidas** da semana (em vez de falta);
* se até o último dia de trabalho da semana ele não folgou, esse último dia é a folga — se trabalhar
  nele, todo o tempo é hora extra (folga trabalhada).

A escolha é feita em ordem cronológica, então um dia já classificado não muda depois.
Feriados não contam como a folga da semana.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta

from app.calculation.workday import ABSENT, DayInput, DayResult, Rules, calculate_day

WEEKLY_DAY_OFF = "WEEKLY_DAY_OFF"


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _is_candidate(inp: DayInput, rotating: Callable[[date], bool]) -> bool:
    return (
        inp.employed
        and inp.tracked
        and not inp.holiday
        and inp.schedule is not None
        and rotating(inp.day)
    )


def calculate_days(
    inputs: Sequence[DayInput],
    rules: Rules,
    now: datetime,
    rotating: Callable[[date], bool],
    is_candidate_day: Callable[[date], bool],
) -> list[DayResult]:
    """Calcula dias consecutivos aplicando a folga semanal.

    `inputs` deve começar numa segunda-feira (ou na admissão) para a semana inicial ser avaliada
    inteira. `is_candidate_day(d)` diz se `d` é dia de trabalho elegível para folga, inclusive
    para datas além de `inputs` (necessário para achar o último dia da semana).
    """
    used: set[date] = set()
    results: list[DayResult] = []
    for inp in inputs:
        normal = calculate_day(inp, rules, now)
        week = week_start(inp.day)
        if not _is_candidate(inp, rotating) or week in used:
            results.append(normal)
            continue
        later_candidates = any(
            is_candidate_day(inp.day + timedelta(days=n)) for n in range(1, 7 - inp.day.weekday())
        )
        if normal.status == ABSENT or not later_candidates:
            used.add(week)
            off = calculate_day(replace(inp, schedule=None), rules, now)
            results.append(replace(off, flags=(*off.flags, WEEKLY_DAY_OFF)))
        else:
            results.append(normal)
    return results
