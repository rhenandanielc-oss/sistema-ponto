"""Logs no stdout: JSON (produção) ou texto (desenvolvimento), sempre com o id da requisição.

Nunca registrar senhas, tokens, cookies, imagens, templates biométricos nem a query string
(ela pode conter nomes pesquisados) — SECURITY.md §7.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Literal

from app.core.request_context import current_request_id

# Campos extras aceitos em `logger.info(..., extra={...})`.
EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "ip", "error_code")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            entry["request_id"] = request_id
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        extras = " ".join(f"{f}={getattr(record, f)}" for f in EXTRA_FIELDS if hasattr(record, f))
        return f"{text} {extras}" if extras else text


def configure_logging(log_format: Literal["json", "text"], level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log_format == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Os logs do uvicorn passam pelo mesmo formato; o de acesso é substituído pelo nosso
    # (o dele inclui a query string).
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
