"""Limitação de taxa em memória (janela deslizante) — SECURITY.md §6.

Limite por processo: com vários workers o limite efetivo é multiplicado pelo número de processos.
Atrás de um proxy reverso, o uvicorn deve rodar com --proxy-headers para que o IP real seja usado.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, limit: int, window_seconds: int) -> int | None:
        """Registra uma tentativa. Devolve os segundos de espera se o limite foi excedido."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(bucket, key)]
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(window_seconds - (now - hits[0])) + 1)
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def rate_limit(bucket: str, limit: int, window_seconds: int = 60) -> Callable[[Request], None]:
    """Dependência FastAPI: limita requisições por IP de origem."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        key = request.client.host if request.client else "desconhecido"
        retry_after = limiter.hit(bucket, key, limit, window_seconds)
        if retry_after is not None:
            raise AppError(
                429,
                "RATE_LIMITED",
                "Muitas tentativas. Aguarde um pouco e tente novamente.",
                {"retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
