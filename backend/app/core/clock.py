"""Fonte única de tempo do backend.

Todo código que precisa do "agora" usa estas funções, para que os testes possam controlar o relógio
com `freeze`. Em produção o valor é sempre o relógio do servidor
(horário oficial — ARCHITECTURE.md §5).
"""

from datetime import UTC, date, datetime

from app.core.config import get_settings

_frozen: datetime | None = None


def now_utc() -> datetime:
    return _frozen if _frozen is not None else datetime.now(UTC)


def today_local() -> date:
    return now_utc().astimezone(get_settings().tz).date()


def freeze(value: datetime | None) -> None:
    """Somente para testes: fixa (ou libera, com None) o relógio do backend."""
    global _frozen
    if value is not None and value.tzinfo is None:
        raise ValueError("Use datetime com fuso horário.")
    _frozen = value
