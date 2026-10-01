"""Ciclo de pagamento do funcionário (BUSINESS-RULES.md §11).

O ciclo termina no dia do pagamento (inclusive) e começa no dia seguinte ao pagamento anterior.
Ex.: pagamento dia 5 → ciclo de 06/08 a 05/09, pago em 05/09.
Se o dia não existir no mês (ex.: 31 em fevereiro), vale o último dia do mês.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class PayPeriod:
    start: date
    end: date  # = data do pagamento

    @property
    def payment_date(self) -> date:
        return self.end


def payment_date_in(year: int, month: int, payday: int) -> date:
    if not 1 <= payday <= 31:
        raise ValueError("O dia do pagamento deve estar entre 1 e 31.")
    return date(year, month, min(payday, calendar.monthrange(year, month)[1]))


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def period_ending_in(year: int, month: int, payday: int) -> PayPeriod:
    """Ciclo cujo pagamento cai no mês informado."""
    end = payment_date_in(year, month, payday)
    prev_year, prev_month = _shift_month(year, month, -1)
    start = payment_date_in(prev_year, prev_month, payday) + timedelta(days=1)
    return PayPeriod(start=start, end=end)


def period_containing(day: date, payday: int) -> PayPeriod:
    """Ciclo de pagamento que contém a data (ex.: hoje → ciclo em andamento)."""
    current = period_ending_in(day.year, day.month, payday)
    if day <= current.end:
        return current
    next_year, next_month = _shift_month(day.year, day.month, 1)
    return period_ending_in(next_year, next_month, payday)
