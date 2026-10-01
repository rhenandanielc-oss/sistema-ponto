# Backend — Sistema de Ponto

API REST em Python 3.12 + FastAPI + PostgreSQL. Arquitetura em `../ARCHITECTURE.md`.

## Rodar com Docker

```bash
cp .env.example .env          # na raiz do repositório; preencha POSTGRES_PASSWORD e JWT_SECRET
docker compose up --build     # API em http://localhost:8000, documentação em /api/docs
docker compose exec backend python -m app.cli create-admin --email voce@empresa.com --name "Seu Nome"
```

A senha do administrador é pedida no terminal. Não existe administrador ou senha padrão.

Produção (HTTPS, backup, limpeza diária): `../DEPLOY.md`.

## Comandos de servidor

```bash
python -m app.cli create-admin --email voce@empresa.com --name "Seu Nome"  # senha pedida no terminal
python -m app.cli maintenance        # limpeza diária (agendada em produção pelo serviço scheduler)
python -m app.cli purge-biometrics   # só o expurgo da biometria excluída há 30+ dias
python -m app.cli download-models    # baixa e confere os modelos de reconhecimento facial
python -m app.cli export-openapi     # OpenAPI para gerar os tipos do frontend
```

## Testes

```bash
docker compose --profile test run --rm tests
```

## Desenvolvimento local (sem Docker)

Requer [uv](https://docs.astral.sh/uv/) e um PostgreSQL 16.

```bash
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://ponto:SENHA@localhost:5432/ponto
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Testes (o banco indicado é apagado e recriado a cada execução)
TEST_DATABASE_URL=postgresql+psycopg://ponto:SENHA@localhost:5432/ponto_test uv run pytest

# Qualidade
uv run ruff check . && uv run ruff format --check . && uv run mypy app
```

## Migrations

Toda alteração de banco é feita por migration Alembic em `migrations/versions/`:

```bash
uv run alembic revision --autogenerate -m "descrição"
uv run alembic upgrade head
uv run alembic check   # confirma que modelos e migrations estão em sincronia
```
