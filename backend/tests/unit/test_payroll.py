"""Ciclo de pagamento (BUSINESS-RULES.md §11)."""

from datetime import date

import pytest

from app.calculation.payroll import PayPeriod, period_containing, period_ending_in


@pytest.mark.parametrize(
    ("day", "payday", "expected"),
    [
        # Pagamento dia 5: ciclo de 06 do mês anterior até 05.
        (date(2026, 9, 1), 5, PayPeriod(date(2026, 8, 6), date(2026, 9, 5))),
        (
            date(2026, 9, 5),
            5,
            PayPeriod(date(2026, 8, 6), date(2026, 9, 5)),
        ),  # dia do pagamento entra
        (date(2026, 9, 6), 5, PayPeriod(date(2026, 9, 6), date(2026, 10, 5))),
        # Virada de ano.
        (date(2026, 12, 20), 10, PayPeriod(date(2026, 12, 11), date(2027, 1, 10))),
        (date(2027, 1, 3), 10, PayPeriod(date(2026, 12, 11), date(2027, 1, 10))),
        # Pagamento dia 1: ciclo de 02 do mês anterior até 01.
        (date(2026, 9, 1), 1, PayPeriod(date(2026, 8, 2), date(2026, 9, 1))),
        # Dia 31: em meses curtos vale o último dia.
        (date(2026, 2, 15), 31, PayPeriod(date(2026, 2, 1), date(2026, 2, 28))),
        (date(2026, 3, 1), 31, PayPeriod(date(2026, 3, 1), date(2026, 3, 31))),
        (date(2026, 4, 30), 31, PayPeriod(date(2026, 4, 1), date(2026, 4, 30))),
        (date(2028, 2, 29), 30, PayPeriod(date(2028, 1, 31), date(2028, 2, 29))),  # bissexto
    ],
)
def test_period_containing(day: date, payday: int, expected: PayPeriod) -> None:
    assert period_containing(day, payday) == expected


def test_consecutive_periods_cover_every_day_once() -> None:
    for payday in (1, 5, 15, 28, 29, 30, 31):
        previous_end = period_ending_in(2025, 12, payday).end
        for month in range(1, 13):
            period = period_ending_in(2026, month, payday)
            assert (period.start - previous_end).days == 1, (payday, month)
            assert period.start <= period.end
            previous_end = period.end


def test_invalid_payday() -> None:
    with pytest.raises(ValueError):
        period_containing(date(2026, 9, 1), 0)
    with pytest.raises(ValueError):
        period_containing(date(2026, 9, 1), 32)
