"""Dados da requisição atual (id, IP, user agent), usados pela auditoria e pelos erros."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request, Response


@dataclass(frozen=True)
class RequestInfo:
    request_id: str
    ip: str | None
    user_agent: str | None


access_logger = logging.getLogger("app.access")

_current: ContextVar[RequestInfo | None] = ContextVar("request_info", default=None)


def current_request() -> RequestInfo | None:
    return _current.get()


def current_request_id() -> str | None:
    info = _current.get()
    return info.request_id if info else None


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    info = RequestInfo(
        request_id=uuid.uuid4().hex,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    token = _current.set(info)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,  # sem query string
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "ip": info.ip,
            },
        )
    finally:
        _current.reset(token)
    response.headers["X-Request-ID"] = info.request_id
    return response
