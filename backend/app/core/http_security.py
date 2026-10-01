"""Cabeçalhos de segurança e limite de tamanho do corpo (SECURITY.md §6)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.request_context import current_request_id

MAX_BODY_BYTES = 1024 * 1024  # 1 MB (o frame do kiosk é um JPEG pequeno)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",  # respostas da API contêm dados pessoais
}


async def security_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
        return JSONResponse(
            {
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Requisição muito grande.",
                    "details": {"max_bytes": MAX_BODY_BYTES},
                    "request_id": current_request_id(),
                }
            },
            status_code=413,
        )
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response
