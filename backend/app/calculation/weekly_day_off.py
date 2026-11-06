"""Folga semanal em qualquer dia (BUSINESS-RULES.md §3.2).

Para funcionários com essa opção no horário, cada semana (segunda a domingo) tem uma folga
(ou duas, nas semanas que o horário marca como "semana de 2 folgas"):
* é o **primeiro dia de trabalho sem batidas** da semana (em vez de falta);
* se faltam tantos dias de trabalho na semana quantas folgas ainda devem ser dadas, esses últimos
  dias são a folga — se trabalhar neles, todo o tempo é hora extra (folga trabalhada).

A escolha é feita em ordem cronológica, então um dia já classificado não muda depois.
Feriados não contam como a folga da semana.

Semana incompleta (parte antes do início do uso do sistema ou da admissão): a folga pode ter
acontecido nos dias que o sistema não conhece, então o último dia **não** é forçado como folga.
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
    quota: Callable[[date], int] | None = None,
) -> list[DayResult]:
    """Calcula dias consecutivos aplicando a folga semanal.

    `inputs` deve começar numa segunda-feira (ou na admissão) para a semana inicial ser avaliada
    inteira. `is_candidate_day(d)` diz se `d` é dia de trabalho elegível para folga, inclusive
    para datas além de `inputs` (necessário para achar o último dia da semana). `quota(d)` diz
    quantas folgas a semana de `d` tem (padrão 1).
    """
    taken: dict[date, int] = {}
    partial: set[date] = set()  # semanas com dias antes do início do controle ou da admissão
    results: list[DayResult] = []
    for inp in inputs:
        normal = calculate_day(inp, rules, now)
        week = week_start(inp.day)
        if not inp.employed or not inp.tracked:
            partial.add(week)
        if not _is_candidate(inp, rotating):
            results.append(normal)
            continue
        owed = (quota(inp.day) if quota else 1) - taken.get(week, 0)
        if owed <= 0:
            results.append(normal)
            continue
        later_candidates = sum(
            is_candidate_day(inp.day + timedelta(days=n)) for n in range(1, 7 - inp.day.weekday())
        )
        last_days = later_candidates < owed and week not in partial
        if normal.status == ABSENT or last_days:
            taken[week] = taken.get(week, 0) + 1
            off = calculate_day(replace(inp, schedule=None), rules, now)
            results.append(replace(off, flags=(*off.flags, WEEKLY_DAY_OFF)))
        else:
            results.append(normal)
    return results
