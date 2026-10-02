# ARCHITECTURE.md

# Arquitetura — Sistema de Ponto Eletrônico

> **Status:** Fases 1–6 concluídas: backend, painel do administrador, terminal com reconhecimento facial e produção.
> Instalação do servidor: `DEPLOY.md`. Instalação do terminal: `KIOSK.md`.

---

## 1. Visão geral

```
┌──────────────────────────┐        HTTPS (JSON/REST)        ┌───────────────────────────┐
│ Frontend (SPA)           │ ──────────────────────────────▶ │ Backend (API REST)        │
│ React + TS + Vite        │                                 │ Python 3.12 + FastAPI     │
│                          │ ◀────────────────────────────── │                           │
│ • Painel administrativo  │                                 │ • Login do administrador  │
│ • Kiosk (/kiosk)         │   frame JPEG do rosto (kiosk)   │ • Funcionários / horários │
│   - câmera (getUserMedia)│ ──────────────────────────────▶ │ • Registros de ponto      │
│   - detecção local (UX)  │                                 │ • Motor de cálculo        │
└──────────────────────────┘                                 │ • Biometria (ONNX local)  │
                                                             │ • Auditoria               │
                                                             └─────────────┬─────────────┘
                                                                           │ SQL
                                                             ┌─────────────▼─────────────┐
                                                             │ PostgreSQL 16             │
                                                             └───────────────────────────┘
```

Tudo roda em contêineres Docker, orquestrados por Docker Compose: `docker-compose.yml` (desenvolvimento) e
`docker-compose.prod.yml` (produção). Em produção o **Caddy** faz a terminação TLS (Let's Encrypt ou CA interna) e
encaminha ao nginx do frontend, que serve a SPA e repassa `/api` ao backend; o kiosk **exige HTTPS** porque
navegadores só liberam a câmera em contexto seguro. Serviços auxiliares: `scheduler` (limpeza diária) e `backup`
(`pg_dump` diário). Detalhes em `DEPLOY.md`.

---

## 2. Decisão de tecnologia do backend

### 2.1 Opções analisadas

| Critério | Python + FastAPI | Node + NestJS (TypeScript) | Java + Spring Boot |
|---|---|---|---|
| Linguagem única com o frontend | Não | **Sim** | Não |
| Ecossistema de visão computacional / ONNX | **Excelente** (onnxruntime, OpenCV, NumPy) | Limitado (onnxruntime-node existe, OpenCV fraco) | Razoável |
| Validação de dados | **Pydantic v2** | class-validator / zod | Bean Validation |
| OpenAPI | **Gerado automaticamente** | Via decorators | Via springdoc |
| Migrações | Alembic | Prisma / TypeORM | Flyway |
| Testes | pytest (muito simples para casos de cálculo) | Jest | JUnit |
| Peso operacional | Baixo | Baixo | Alto |

### 2.2 Decisão

**Python 3.12 + FastAPI**, com:

* **SQLAlchemy 2.x** (ORM, modo síncrono) e **Alembic** (migrations versionadas);
* **Pydantic v2** (schemas de entrada/saída e configuração via `pydantic-settings`);
* **psycopg 3** (driver PostgreSQL);
* **argon2-cffi** (hash de senha);
* **PyJWT** (tokens de acesso);
* **OpenCV** (módulo DNN executa os modelos ONNX da biometria, ver `BIOMETRICS.md`);
* **pytest** (testes), **ruff** (lint/format), **mypy** (tipagem).

**Motivo:** a biometria é a parte de maior risco do projeto e precisa rodar no servidor
(ver `BIOMETRICS.md`); Python tem o melhor suporte para isso. O motor de cálculo de jornada é
lógica pura e fica muito legível e testável em Python. O `.gitignore` do repositório já previa
Python/FastAPI.

**Custo aceito:** duas linguagens (TS no frontend, Python no backend). Os tipos do frontend serão
gerados a partir do OpenAPI do backend (Fase 4) para evitar divergência manual.

**Por que síncrono:** a carga esperada (dezenas a poucas centenas de funcionários por instalação)
não justifica a complexidade do async. Inferência biométrica é CPU-bound e roda em threadpool de
qualquer forma.

---

## 3. Frontend

* React 19 + TypeScript + Vite;
* Tailwind CSS;
* React Router;
* TanStack React Query (cache e estado de servidor);
* Interface em português.

Regras:

* o frontend **não calcula** jornada, saldo nem banco de horas — apenas exibe o que o backend retorna;
* o frontend **não envia horário** de registro de ponto — o servidor define o horário oficial;
* nenhum segredo no bundle; somente a URL pública da API em variável `VITE_*`.

O kiosk é a mesma SPA na rota `/kiosk`, autenticada com **credencial de dispositivo** (não de usuário).

### 3.1 Rotas

| Rota | Quem usa | Conteúdo |
|---|---|---|
| `/kiosk` | Funcionário (rosto) | Reconhecimento facial → escolher tipo de batida ou ver o próprio banco de horas |
| `/login` | Administrador | E-mail e senha |
| `/funcionarios` | Administrador | Cadastro, edição, ativação/desativação, pesquisa, **nome, horário fixo (entrada, almoço, saída) por dia da semana e rosto** |
| `/historico` | Administrador | Batidas com filtros (funcionário, hoje, semana, mês, período) e ajustes |
| `/banco-de-horas` | Administrador | Banco de horas de qualquer funcionário, por período, com detalhe diário |
| `/pagamento` | Administrador | Horas de cada funcionário no ciclo de pagamento (o administrador multiplica pelo valor da hora) |
| `/admin` | Administrador | Feriados, dispositivos (kiosks), administradores, configurações, auditoria |

A rota `/jornadas` prevista no `MASTER-PROMPT.md` foi incorporada a `/funcionarios`: o horário fixo é informado
no cadastro do funcionário (decisão do responsável, 2026-10-01). `/jornadas` redireciona para `/funcionarios`.
Detalhes do funcionário em `/funcionarios/:id`; banco de horas de um funcionário em `/banco-de-horas/:id`.

### 3.2 Implementação (Fase 4)

* `src/api/client.ts`: `fetch` com o token em memória; em 401 tenta **uma** renovação pelo cookie de refresh
  (renovações simultâneas são compartilhadas) e repete a requisição; se falhar, volta ao login.
* `src/api/schema.d.ts`: tipos gerados do OpenAPI do backend (`npm run gen:api`), evitando divergência manual.
* `src/lib/auth.tsx`: sessão do administrador; ao abrir a página, a sessão é recuperada pelo cookie.
* Formatação de datas lê o texto que a API devolve (já no fuso da empresa), sem conversão pelo fuso do navegador.
* Produção: `frontend/Dockerfile` gera o build e o serve por **nginx**, que encaminha `/api` ao backend
  (mesma origem para o cookie) e envia CSP e cabeçalhos de segurança.

---

## 4. Organização do repositório

`backend/` (Fase 1), `frontend/` (Fase 4), `backend/app/biometrics/` e `frontend/src/kiosk/` (Fase 5).

```
sistema-ponto/
├── backend/
│   ├── app/
│   │   ├── main.py              # criação do app FastAPI, middlewares, routers
│   │   ├── cli.py               # comandos de servidor (create-admin, maintenance, download-models, ...)
│   │   ├── core/                # config, relógio, segurança (JWT, hash), erros, contexto da requisição
│   │   ├── db/                  # engine, sessão, base declarativa
│   │   ├── models/              # modelos SQLAlchemy
│   │   ├── schemas/             # modelos Pydantic (entrada/saída)
│   │   ├── api/                 # routers por recurso (auth, admins, employees, kiosk, ...)
│   │   ├── services/            # regras de negócio e transações
│   │   ├── calculation/         # motor de cálculo de jornada (funções puras, sem I/O)
│   │   └── biometrics/          # detecção, extração de template, matching
│   ├── migrations/              # Alembic
│   ├── tests/
│   │   ├── unit/                # motor de cálculo, regras puras
│   │   └── integration/         # API + PostgreSQL real
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/  components/  api/  hooks/  routes/
│   │   └── kiosk/
│   ├── package.json
│   └── Dockerfile
├── deploy/                      # Caddyfile, backup.sh, restore.sh (produção)
├── docker-compose.yml           # desenvolvimento e testes
├── docker-compose.prod.yml      # produção (DEPLOY.md)
├── .env.example
└── *.md                         # documentação (este arquivo, DATABASE.md, ...)
```

### 4.1 Camadas do backend

```
api (routers)  →  services  →  models / db
                      │
                      └──→ calculation (puro)   biometrics (puro + modelo ONNX)
```

* **api:** HTTP apenas — parse, autenticação, autorização, chamada de serviço, serialização.
* **services:** regras de negócio, transações, escrita de auditoria.
* **calculation:** recebe dados já carregados (registros, jornada, feriados) e devolve o resultado.
  Não acessa banco nem relógio — isso torna os casos de teste obrigatórios determinísticos.
* **biometrics:** encapsula o modelo; a API nunca manipula vetores diretamente.

---

## 5. Tempo e timezone

Decisão crítica para um sistema de ponto:

* Todo instante é gravado como `timestamptz` (UTC no banco).
* O **horário oficial** do registro é o relógio do servidor (`app/core/clock.py`, única fonte de "agora" do backend);
  o cliente não envia horário.
* A empresa tem um **fuso de referência** configurável (`APP_TIMEZONE`, padrão `America/Sao_Paulo`).
  Datas de jornada, "hoje", "semana", "mês", feriados e horários de escala são interpretados nesse fuso.
* O servidor deve manter o relógio sincronizado por NTP (requisito de deploy, Fase 6).
* O motor de cálculo trabalha com `datetime` com fuso (`zoneinfo`), nunca com horários "ingênuos".

---

## 6. Autenticação (resumo — detalhes em `SECURITY.md`)

* **Dois perfis apenas:** Administrador e Funcionário.
* **Administrador:** único com senha. Login com e-mail + senha → access token JWT curto (15 min) + refresh token
  opaco em cookie `HttpOnly`, `Secure`, `SameSite=Strict`, armazenado com hash e rotacionado.
* **Funcionário:** sem senha. É identificado pelo rosto no kiosk; o servidor emite um token de identificação de 60 s
  que permite registrar a batida ou consultar o próprio banco de horas.
* **Kiosks:** cada terminal é um **dispositivo** cadastrado pelo administrador, com token próprio
  (exibido uma única vez, armazenado com hash), que só acessa os endpoints do kiosk.

---

## 7. Concorrência e integridade

* Criação de registro de ponto ocorre em transação com `SELECT ... FOR UPDATE` na linha do funcionário,
  serializando registros simultâneos do mesmo funcionário (ex.: dois toques rápidos no kiosk).
* Restrições únicas no banco são a última linha de defesa contra duplicidade (ver `DATABASE.md`).
* Registros de ponto são **imutáveis**; correções são feitas por ajustes auditados.

---

## 8. Observabilidade

* Logs no stdout (`app/core/logging.py`): JSON em produção (`LOG_FORMAT=json`), texto em desenvolvimento.
  Cada requisição gera um evento `app.access` com método, caminho **sem query string**, status, duração, IP e
  `request_id` (o mesmo devolvido em `X-Request-ID` e nos erros). Os logs do uvicorn usam o mesmo formato.
* Endpoints `GET /health/live` e `GET /health/ready` (este verifica o banco), usados pelos healthchecks do Docker.
* Nunca registrar em log: senhas, tokens, imagens, templates biométricos.

## 8.1 Desempenho

Resultados calculados sob demanda. Relatórios de vários funcionários carregam configurações e feriados uma vez e
fazem um único cálculo por funcionário (admissão até o fim do período). Medições em `DEPLOY.md` §9.
A API roda com um processo (limitador de taxa em memória); a inferência facial é CPU-bound e roda no pool de
threads do FastAPI.

---

## 9. Decisões registradas

| Data | Decisão | Onde |
|---|---|---|
| 2026-10-01 | Backend em Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic | §2 |
| 2026-10-01 | Horário oficial = relógio do servidor; armazenamento em UTC; fuso de referência configurável | §5 |
| 2026-10-01 | Kiosk autenticado por token de dispositivo, não por usuário | §6 |
| 2026-10-01 | Registros imutáveis; correção por ajuste auditado | §7, `BUSINESS-RULES.md` |
| 2026-10-01 | Reconhecimento facial processado no servidor com modelo local | `BIOMETRICS.md` |
| 2026-10-01 | Perfis: somente Administrador (senha) e Funcionário (rosto) | §6, `SECURITY.md` |
| 2026-10-01 | Horário fixo por funcionário, informado no cadastro (com vigência); `/jornadas` incorporada a `/funcionarios` | §3.1, `BUSINESS-RULES.md` §3 |
| 2026-10-01 | Funcionário consulta o próprio banco de horas no kiosk pelo rosto | `BUSINESS-RULES.md` §9.1 |
| 2026-10-01 | Produção com Caddy (TLS automático), um processo uvicorn, limpeza e backup em contêineres próprios | §1, `DEPLOY.md` |
| 2026-10-01 | Histórico imutável garantido por triggers no banco | `DATABASE.md`, `SECURITY.md` §8 |
| 2026-10-01 | Modo "um computador só" (`docker-compose.local.yml`): notebook Windows é servidor e terminal, acesso só por `http://localhost` | `INSTALACAO-WINDOWS.md` |
