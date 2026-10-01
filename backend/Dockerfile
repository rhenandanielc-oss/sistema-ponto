FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir "uv==0.8.*"

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Modelos de reconhecimento facial (YuNet MIT, SFace Apache 2.0), conferidos por SHA-256.
ENV FACE_MODELS_DIR=/app/models
RUN uv run --no-sync python -m app.cli download-models --dir /app/models

RUN useradd --system --uid 10001 ponto
USER ponto

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')"

# Aplica as migrations e sobe a API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Imagem de testes: inclui dependências de desenvolvimento.
FROM base AS test
USER root
RUN uv sync --frozen --no-install-project
COPY tests ./tests
COPY pyproject.toml ./
USER ponto
CMD ["pytest", "-q"]
