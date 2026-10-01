from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admins,
    auth,
    devices,
    employees,
    health,
    holidays,
    hour_bank,
    kiosk,
    time_records,
)
from app.api import settings as settings_api
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.request_context import request_context_middleware

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sistema de Ponto",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (
        health,
        auth,
        admins,
        employees,
        hour_bank,
        time_records,
        holidays,
        devices,
        settings_api,
        kiosk,
    ):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
