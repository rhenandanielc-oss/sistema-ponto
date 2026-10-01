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
from app.api import audit as audit_api
from app.api import settings as settings_api
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.http_security import security_middleware
from app.core.request_context import request_context_middleware

API_PREFIX = "/api/v1"

API_DESCRIPTION = """
API do sistema de ponto eletrônico com reconhecimento facial.

* **Administrador**: `Authorization: Bearer <token>` obtido em `/auth/login`.
* **Terminal (kiosk)**: `Authorization: Device <token>` obtido ao cadastrar o dispositivo.
* Instantes são devolvidos no fuso da empresa; períodos (`date_from`/`date_to`) são inclusivos.
* Erros seguem o formato `{"error": {"code", "message", "details", "request_id"}}`.
"""

TAGS = [
    {"name": "autenticação", "description": "Login, renovação e saída do administrador."},
    {"name": "administradores", "description": "Únicos usuários com senha."},
    {
        "name": "funcionários",
        "description": "Cadastro, horário fixo (dias, entrada, saída, almoço).",
    },
    {
        "name": "registros de ponto",
        "description": "Histórico de batidas e ajustes do administrador.",
    },
    {"name": "cálculo e banco de horas", "description": "Resultado diário, saldos e lançamentos."},
    {"name": "feriados", "description": "Feriados fixos e recorrentes."},
    {"name": "dispositivos", "description": "Terminais de ponto autorizados."},
    {"name": "configurações", "description": "Tolerâncias e parâmetros da empresa."},
    {"name": "auditoria", "description": "Trilha de ações relevantes (somente leitura)."},
    {"name": "kiosk", "description": "Endpoints usados pelo terminal de ponto."},
    {"name": "saúde", "description": "Verificações para o orquestrador."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sistema de Ponto",
        version="0.3.0",
        description=API_DESCRIPTION,
        openapi_tags=TAGS,
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
    # O último registrado roda primeiro: o contexto (request_id) envolve a checagem de segurança.
    app.middleware("http")(security_middleware)
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
        audit_api,
        holidays,
        devices,
        settings_api,
        kiosk,
    ):
        api.include_router(module.router)
    api.include_router(hour_bank.summary_router)
    app.include_router(api)
    return app


app = create_app()
