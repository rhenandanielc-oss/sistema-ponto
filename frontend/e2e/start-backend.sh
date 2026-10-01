#!/usr/bin/env sh
# Sobe o backend para os testes E2E com um banco descartável (o esquema é apagado a cada execução).
# Requer E2E_DATABASE_URL apontando para um banco exclusivo de testes.
set -eu
: "${E2E_DATABASE_URL:?defina E2E_DATABASE_URL (banco exclusivo para testes E2E)}"
cd "$(dirname "$0")/../../backend"
export DATABASE_URL="$E2E_DATABASE_URL" ENVIRONMENT=development COOKIE_SECURE=false RATE_LIMIT_ENABLED=false
# Motor facial falso: a câmera simulada do Chromium não tem rosto. Proibido em produção pela configuração.
export FACE_ENGINE=fake
export JWT_SECRET="e2e-only-jwt-key-0123456789abcdef0123456789"
uv run python -c "
from sqlalchemy import create_engine, text
with create_engine('$E2E_DATABASE_URL').begin() as c:
    c.execute(text('DROP SCHEMA public CASCADE; CREATE SCHEMA public'))
"
uv run alembic upgrade head
echo "senha-e2e-segura" | uv run python -m app.cli create-admin --email admin@e2e.com --name "Admin E2E" --password-stdin
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
