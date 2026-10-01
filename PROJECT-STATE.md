# PROJECT-STATE.md

# Sistema de Ponto Eletrônico com Reconhecimento Facial

Este arquivo representa o estado atual do projeto.

Ele deve ser atualizado pelo Claude Code ao final de cada etapa significativa.

---

# STATUS GERAL

**Status:** EM ANDAMENTO

**Fase atual:** Fase 4 — Frontend (CONCLUÍDA) → próxima: Fase 5 — Biometria e Kiosk

**Última atualização:** 2026-10-01

**Último commit:** `feat: payday and payroll hours per employee` (branch `claude/oi-xu1bph`; ver `git log`)

**Próxima ação:** Iniciar a Fase 5 — reconhecimento facial e terminal de ponto (kiosk).

---

# FASES

## Fase 0 — Arquitetura

**Status:** CONCLUÍDA (2026-10-01)

### Objetivos

* definir arquitetura;
* definir banco;
* definir API;
* definir segurança;
* definir regras de negócio;
* definir arquitetura biométrica;
* definir estratégia de testes.

### Entregáveis

* [x] `ARCHITECTURE.md` — stack, camadas, estrutura de pastas, timezone, concorrência
* [x] `DATABASE.md` — tabelas por fase, restrições de integridade e duplicidade
* [x] `API.md` — convenções (paginação, filtros, ordenação, erros) e endpoints por fase
* [x] `SECURITY.md` — perfis (Administrador/Funcionário), ameaças, autenticação, kiosk, segredos, auditoria
* [x] `BUSINESS-RULES.md` — horário fixo do funcionário, sequência, duplicidade, dia de jornada, motor de cálculo, tolerância, noturno, feriados, banco de horas, consulta pelo kiosk
* [x] `BIOMETRICS.md` — comparação de alternativas, decisão, armazenamento, retenção, riscos
* [x] `TEST-PLAN.md` — estratégia e casos obrigatórios com exemplos numéricos (C01–C24, R01–R17, A01–A13)

### Testes

Não aplicável (fase apenas de documentação; nenhum código criado). Os exemplos numéricos do
`TEST-PLAN.md` foram conferidos manualmente (dias da semana de set/2026 e contas de minutos).

### Decisões

Ver seção DECISÕES TÉCNICAS.

---

# Fase 1 — Backend base

**Status:** CONCLUÍDA (2026-10-01)

### Objetivos

* [x] PostgreSQL 16 (Docker Compose: `db` para desenvolvimento, `test-db` descartável para testes)
* [x] Docker (`backend/Dockerfile` multi-stage: `base` = API, `test` = testes)
* [x] migrations (Alembic, `0001` — inclui `EXCLUDE` contra vigências sobrepostas)
* [x] modelos (`admins`, `refresh_tokens`, `employees`, `employee_schedules`, `employee_schedule_days`, `audit_logs`, `settings`)
* [x] administradores (único perfil com senha; primeiro criado por `python -m app.cli create-admin`)
* [x] autenticação (JWT 15 min + refresh rotacionado em cookie HttpOnly, detecção de reuso, bloqueio após 5 falhas)
* [x] autorização (toda rota administrativa exige administrador ativo; teste automático cobre todas as rotas)
* [x] funcionários (cadastro, edição, ativação/desativação, pesquisa, paginação, ordenação, histórico via auditoria)
* [x] horário fixo no cadastro do funcionário (entrada, almoço, retorno, saída por dia da semana; vigência; carga diária calculada)

### Arquivos importantes

* `backend/app/main.py` — criação da aplicação
* `backend/app/core/` — `config.py`, `clock.py` (única fonte de "agora"), `security.py`, `errors.py`, `request_context.py`
* `backend/app/calculation/schedule.py` — validação do horário e carga planejada (puro; será usado pelo motor da Fase 2)
* `backend/app/services/` — `auth_service.py`, `admin_service.py`, `employee_service.py`, `audit.py`
* `backend/app/api/` — `auth.py`, `admins.py`, `employees.py`, `health.py`, `deps.py`
* `backend/migrations/versions/0001_phase_1_base_schema.py`
* `backend/tests/` — 81 testes (unitários + integração com PostgreSQL real)
* `docker-compose.yml`, `.env.example`, `backend/README.md`

### Testes

81 testes passando (ver TESTES DA ÚLTIMA SESSÃO). Cobertura do `TEST-PLAN.md`: A01–A10 e §6 completos;
A11–A13 são do kiosk (Fase 5).

---

# Fase 2 — Registros e cálculo

**Status:** CONCLUÍDA (2026-10-01)

### Objetivos

* [x] registros ENTRY, LUNCH_EXIT, LUNCH_RETURN, EXIT (horário oficial do servidor; serviço pronto para o kiosk da Fase 5)
* [x] validação de sequência (máquina de estados; almoço livre em qualquer horário)
* [x] prevenção de duplicidade (mesmo tipo no dia, batidas a menos de 2 min, índice único parcial, bloqueio por funcionário)
* [x] cálculo de jornada (motor puro `app/calculation/workday.py`)
* [x] horas extras, atrasos, saída antecipada, horas faltantes, tolerância CLT
* [x] faltas, registros incompletos, dia em andamento, dias futuros
* [x] banco de horas (saldo anterior, detalhamento diário, lançamentos manuais, saldo final)
* [x] feriados (fixos e recorrentes)
* [x] finais de semana / folgas trabalhadas
* [x] turno noturno (dia de jornada pela entrada; minutos noturnos e hora reduzida)
* [x] ajustes do administrador (incluir batida esquecida / anular batida errada, com justificativa e auditoria)
* [x] histórico de batidas com filtros, paginação e ordenação
* [x] terminais (kiosk): cadastro, token exibido uma vez, rotação, desativação, `GET /kiosk/ping`
* [x] configurações da empresa (`GET/PATCH /settings`)

### Arquivos importantes

* `backend/app/calculation/records.py` — sequência e dia de jornada (puro)
* `backend/app/calculation/workday.py` — motor de cálculo do dia (puro)
* `backend/app/services/record_service.py` — batidas, ajustes, histórico
* `backend/app/services/hour_bank_service.py` — cálculo por período e banco de horas
* `backend/app/services/{holiday,device,settings}_service.py`
* `backend/app/api/{time_records,hour_bank,holidays,devices,settings,kiosk}.py`
* `backend/migrations/versions/0002_flexible_lunch.py`, `0003_phase_2_timekeeping.py`

### Testes

165 testes passando. Cobertura do `TEST-PLAN.md`: C01–C24 (+ C05b, C05c), R01–R18 (inclui concorrência real com
duas conexões), banco de horas via API, feriados, terminais e configurações.

---

# Fase 3 — API

**Status:** CONCLUÍDA (2026-10-01)

### Objetivos

* [x] autenticação, administradores, funcionários, horário fixo (Fase 1)
* [x] registros, histórico, cálculos, banco de horas, feriados, terminais, configurações (Fase 2)
* [x] cadastro do horário com dias por nome ("segunda", "sáb"…), horário fixo e almoço; dia extra = hora extra
* [x] auditoria consultável (`GET /audit-logs`: entidade, ação exata ou por prefixo, administrador, período, ordenação)
* [x] resumo do banco de horas de todos (`GET /hour-bank/summary`)
* [x] filtros, paginação e ordenação em todas as listagens
* [x] tratamento de erros padronizado (inclui 413 e 429)
* [x] limitação de taxa (login, refresh, kiosk), cabeçalhos de segurança, limite de 1 MB no corpo
* [x] OpenAPI com descrição e tags documentadas (teste garante que toda rota tem tag declarada)
* [x] testes de integração, incluindo fluxo ponta a ponta de uma semana de trabalho
* [ ] kiosk: identificação, batida e consulta do banco de horas pelo rosto → **Fase 5** (depende da biometria)

### Arquivos importantes

* `backend/app/api/audit.py`, `backend/app/services/audit_query.py`
* `backend/app/api/hour_bank.py` (`summary_router`), `backend/app/services/hour_bank_service.py` (`summary`)
* `backend/app/core/rate_limit.py`, `backend/app/core/http_security.py`
* `backend/tests/integration/test_phase3_api.py`, `test_end_to_end.py`

### Testes

179 testes passando.

---

# Fase 4 — Frontend

**Status:** CONCLUÍDA (2026-10-01)

### Rotas

* [x] `/login`
* [ ] `/kiosk` — página provisória; o terminal com reconhecimento facial é da **Fase 5**
* [x] `/historico`
* [x] `/banco-de-horas` e `/banco-de-horas/:id`
* [x] `/funcionarios` e `/funcionarios/:id`
* [x] ~~`/jornadas`~~ → redireciona para `/funcionarios` (decisão de 2026-10-01)
* [x] `/admin` (abas: feriados, terminais, administradores, configurações, auditoria)

### Funcionalidades

* [x] login / logout; sessão recuperada ao recarregar (cookie de refresh); renovação automática do token
* [x] funcionários: lista com busca, situação e paginação; cadastro com **nome, matrícula, CPF, admissão,
  dias de trabalho, entrada, saída e tempo de almoço**; edição; ativar/desativar; alterar horário com vigência;
  histórico de alterações
* [ ] cadastro do rosto → Fase 5
* [x] histórico: filtros (funcionário, hoje/semana/mês/período, tipo, anuladas), paginação, detalhes,
  incluir batida esquecida, anular batida
* [x] banco de horas: resumo de todos; detalhe diário por funcionário (batidas, previsto, trabalhado, almoço,
  atraso, saída antecipada, saldo, situação e alertas); lançamentos manuais
* [x] administração: feriados, terminais (chave exibida uma vez, nova chave, ativar/desativar),
  administradores, configurações, auditoria
* [x] interface em português, funciona em desktop, tablet e celular
* [x] **pagamento** (adicionado a pedido do responsável): dia do pagamento no cadastro; página `/pagamento` com
  as horas do ciclo de cada funcionário (horas e minutos e horas decimais); ficha mostra o ciclo atual

### Decisões

* Backend: `recorded_at` de ajuste **sem fuso** passa a ser interpretado no fuso da empresa (o navegador não
  conhece o fuso da empresa; o administrador digita a hora do relógio da empresa).
* CLI: `create-admin --password-stdin` (automação) e `export-openapi` (gera os tipos do frontend).
* TypeScript fixado em 5.9 (o plugin de lint e o gerador de tipos ainda não suportam o 6).

### Arquivos importantes

* `frontend/src/api/client.ts`, `frontend/src/api/schema.d.ts` (gerado), `frontend/src/lib/auth.tsx`
* `frontend/src/pages/*.tsx`, `frontend/src/components/*.tsx`
* `frontend/e2e/app.spec.ts`, `frontend/e2e/start-backend.sh`, `frontend/playwright.config.ts`
* `frontend/Dockerfile`, `frontend/nginx.conf`, serviço `frontend` no `docker-compose.yml` (porta 8080)

### Testes

Frontend: ESLint, `tsc`, Vitest (11 testes), build de produção, Playwright E2E (2 testes; 6 execuções seguidas
estáveis no Vite e também contra o build servido pelo nginx com CSP). Backend: 180 testes.

---

# Fase 5 — Biometria e Kiosk

**Status:** PENDENTE

### Objetivos

* [ ] decisão da tecnologia biométrica
* [ ] documentação
* [ ] câmera
* [ ] detecção facial
* [ ] identificação
* [ ] registro (funcionário só escolhe o tipo de batida)
* [ ] consulta do próprio banco de horas pelo rosto
* [ ] confirmação
* [ ] tratamento de erros
* [ ] modo kiosk
* [ ] reconexão
* [ ] HTTPS
* [ ] inicialização automática

---

# Fase 6 — Auditoria e produção

**Status:** PENDENTE

### Objetivos

* [ ] auditoria técnica
* [ ] auditoria de segurança
* [ ] testes finais
* [ ] correção de bugs
* [ ] Docker de produção
* [ ] health checks
* [ ] logs
* [ ] backup
* [ ] migrations de produção
* [ ] `.env.example`
* [ ] documentação de deploy
* [ ] documentação do kiosk

---

# DECISÕES TÉCNICAS

### 2026-10-01 — Backend em Python 3.12 + FastAPI

**Problema:** o MASTER-PROMPT deixa a tecnologia do backend em aberto.
**Opções analisadas:** FastAPI (Python), NestJS (Node/TS), Spring Boot (Java).
**Decisão:** FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + pytest.
**Motivo:** biometria precisa rodar no servidor e Python tem o melhor ecossistema (onnxruntime/OpenCV); motor de cálculo simples de testar.
**Impacto:** duas linguagens; tipos do frontend serão gerados do OpenAPI. Detalhes em `ARCHITECTURE.md` §2.

### 2026-10-01 — Horário oficial, timezone e imutabilidade

**Decisão:** horário oficial = `now()` do servidor; `timestamptz` em UTC; fuso de referência `America/Sao_Paulo` configurável; registros imutáveis, correção apenas por ajuste auditado.
**Motivo:** confiabilidade jurídica e de auditoria. Detalhes em `ARCHITECTURE.md` §5 e `BUSINESS-RULES.md` §4.

### 2026-10-01 — Dia de jornada e jornada noturna

**Decisão:** registros de um ciclo aberto (até 16 h) pertencem ao dia da ENTRY; um ciclo (ENTRY…EXIT) por dia na v1.
**Motivo:** resolve turnos que atravessam a meia-noite sem ambiguidade. `BUSINESS-RULES.md` §4.4.

### 2026-10-01 — Cálculo sob demanda

**Decisão:** resultados diários não são persistidos na v1; calculados a partir dos registros.
**Motivo:** evita inconsistência após ajustes. Cache pode ser adicionado na Fase 6. `DATABASE.md` §4.

### 2026-10-01 — Arquitetura biométrica

**Opções analisadas:** face-api.js, TensorFlow.js, MediaPipe, backend com ONNX local (YuNet + SFace), InsightFace, APIs externas.
**Decisão:** MediaPipe no navegador só para UX (detecção/enquadramento); identificação no servidor com YuNet + SFace (ONNX, local); apenas embeddings cifrados (AES-256-GCM) são armazenados, nunca imagens; registro exige token de identificação emitido pelo servidor.
**Motivo:** privacidade (sem terceiros), confiança (decisão no servidor), licenças permissivas, sem dependência de internet. InsightFace descartado por licença não comercial dos modelos; APIs externas descartadas por LGPD/dependência de internet.
**Impacto:** sem detecção de vivacidade por padrão (risco registrado). Detalhes em `BIOMETRICS.md`.

### 2026-10-01 — Autenticação

**Decisão:** JWT de acesso (15 min, em memória) + refresh opaco rotacionado em cookie HttpOnly, só para administradores; kiosk com token de dispositivo; funcionário identificado por token de identificação de 60 s emitido após o reconhecimento facial. `SECURITY.md`.

### 2026-10-01 — Definições do responsável (alteram o MASTER-PROMPT)

**Problema:** o MASTER-PROMPT prevê perfis/permissões genéricos, jornadas com horários e rota `/jornadas`.
**Decisão do responsável:**
1. Apenas dois perfis: **Administrador** (único com senha) e **Funcionário** (sem senha, identificado pelo rosto).
2. No kiosk o funcionário é reconhecido pela face e **só escolhe o tipo de batida**.
3. O funcionário consulta o **próprio banco de horas** no kiosk, também pelo rosto; o servidor só devolve os dados de quem reconheceu.
4. Cada funcionário tem um **horário fixo** (entrada, almoço, retorno, saída por dia da semana), ainda desconhecido hoje: por isso é informado **no cadastro do funcionário**, junto com o nome e o rosto, com vigência. Com ele o sistema calcula atraso, saída antecipada, horas faltantes e horas extras (tolerância CLT 5/10 min por batida). *(Corrigido em 2026-10-01: a versão anterior falava em "carga horária diária sem horário fixo", por engano.)*
5. Portaria MTP 671/2021 e alternativa à biometria (PIN) **não serão tratadas**.
7. *(2026-10-01)* **Dia do pagamento** no cadastro do funcionário. O sistema calcula **somente as horas** do ciclo
   (do dia seguinte ao pagamento anterior até o dia do pagamento, inclusive; dia inexistente no mês = último dia),
   inclusive em horas decimais; **o administrador multiplica pelo valor da hora**. Nenhum valor em dinheiro é
   guardado. Página `/pagamento`, endpoints `/payroll`, migration `0004`. Ciclo assumido pelo Claude Code —
   o responsável pode pedir outro corte (ex.: fechar alguns dias antes do pagamento).
6. *(2026-10-01)* O horário fixo é **só entrada e saída** (ex.: João, 08:00 – 16:00). **O almoço é livre**: o funcionário
   sai e volta quando quiser e o sistema não recusa almoço fora de hora. O cadastro guarda a **duração prevista do
   almoço** (padrão 60 min, ajustável, pode ser 0), descontada da carga: 08:00–16:00 ⇒ 7 h. Migration `0002`.
**Impacto:** tabelas `roles`/`permissions` removidas (há só `admins`); jornadas FIXED/ROTATING removidas; `/jornadas` incorporada a `/funcionarios`; registro web removido (só kiosk + ajuste do administrador). Documentos atualizados: todos os da Fase 0. `MASTER-PROMPT.md` não foi editado; esta decisão prevalece sobre ele.

---

# DECISÕES PENDENTES (precisam do responsável pelo projeto)

1. **Retenção** dos registros de ponto e da auditoria (prazo da empresa). Não bloqueia a Fase 1.
2. **Valores padrão** (configuráveis, podem ser ajustados depois): tolerância 5 min por batida / 10 min por dia, intervalo mínimo entre batidas 2 min, `max_shift_hours` 16 h, tela do banco de horas no kiosk fecha em 30 s.

Formato recomendado:

### [DATA] — [DECISÃO]

**Problema:**
...

**Opções analisadas:**
...

**Decisão:**
...

**Motivo:**
...

**Impacto:**
...

---

# REGRAS DE NEGÓCIO IMPORTANTES

As regras devem ser detalhadas em `BUSINESS-RULES.md`.

Resumo:

* horário oficial vem do servidor;
* registros possuem sequência;
* registros duplicados devem ser impedidos;
* cálculos acontecem no backend;
* períodos são inclusivos;
* banco de horas depende do cálculo de jornada;
* funcionário inativo não deve registrar ponto;
* alterações relevantes devem possuir auditoria.

---

# SEGURANÇA

Status:

* [x] autenticação (administrador)
* [x] autorização
* [x] proteção de rotas (teste percorre todas as rotas do OpenAPI)
* [x] hash de senha (argon2id)
* [x] expiração de sessão (access 15 min, refresh 8 h, rotação e reuso)
* [x] auditoria de login
* [x] proteção de secrets (`.env` fora do Git; API recusa iniciar em produção com `JWT_SECRET` fraco)
* [x] limitação de taxa (Fase 3; em memória, por processo)
* [x] cabeçalhos de segurança e limite de tamanho de corpo (Fase 3)
* [ ] permissões de banco somente-inserção em `audit_logs` (Fase 6)
* [ ] proteção de biometria
* [ ] controle de acesso
* [ ] HTTPS
* [ ] revisão final

---

# TESTES

## Unitários

* [x] jornada normal
* [x] intervalo
* [x] atraso
* [x] saída antecipada
* [x] hora extra
* [x] falta
* [x] duplicidade
* [x] registro incompleto
* [x] jornada noturna
* [x] feriado
* [x] final de semana
* [x] banco de horas
* [x] período inclusivo

## Integração

* [x] autenticação
* [x] funcionários
* [x] horário fixo dos funcionários
* [x] registros
* [x] cálculos
* [x] histórico
* [x] banco de horas
* [x] auditoria

## Frontend

* [ ] login
* [ ] cadastro
* [ ] histórico
* [ ] banco de horas
* [ ] kiosk

---

# PROBLEMAS CONHECIDOS

### Ordenação por nome diferenciava maiúsculas (corrigido)

**Descrição:** "ana" aparecia depois de "Bruno" na listagem de funcionários.
**Status:** corrigido na Fase 1 (ordenação por `lower(name)`), coberto por teste.

### Horários devolvidos em UTC (corrigido)

**Descrição:** a API devolvia instantes em UTC (`20:00Z`) em vez do fuso da empresa (`17:00-03:00`).
**Status:** corrigido na Fase 2 (`LocalDatetime` em `app/schemas/common.py`), coberto por teste.

### Ambiente do Claude Code na nuvem: build Docker

**Descrição:** neste ambiente o proxy de rede usa certificado próprio e bloqueia `ghcr.io`; o build da imagem só
foi validado com uma cópia temporária do Dockerfile que instala esse certificado (não versionada).
**Impacto:** nenhum fora deste ambiente. O Dockerfile do projeto instala o `uv` via PyPI.
**Status:** sem ação necessária.

Formato:

### Problema

**Descrição:**
...

**Impacto:**
...

**Status:**
...

**Solução:**
...

---

# RISCOS

| Categoria | Risco | Mitigação planejada |
|---|---|---|
| biometria | Fraude com foto/vídeo (sem detecção de vivacidade) | Kiosk supervisionado, auditoria, avaliar anti-spoofing com licença compatível na Fase 5 |
| biometria | Licenças dos modelos (YuNet/SFace) | Confirmar licença dos arquivos exatos na Fase 5 antes de usar |
| privacidade | Biometria é dado sensível (LGPD) | Consentimento, sem imagens, templates cifrados, exclusão e expurgo |
| acesso | Funcionário sem senha: foto/vídeo de colega poderia ser usado para ver o banco de horas dele | Somente leitura dos dados daquele funcionário; auditoria das consultas; anti-spoofing avaliado na Fase 5 |
| timezone | Erros em turnos noturnos e horário de verão | `zoneinfo`, casos C17/R13/R14 |
| concorrência | Registros simultâneos duplicados | `SELECT ... FOR UPDATE` + índice único parcial; teste R08 |
| kiosk | Câmera/rede instáveis | Tratamento de erros e reconexão (Fase 5) |

Possíveis categorias:

* segurança;
* biometria;
* privacidade;
* performance;
* concorrência;
* disponibilidade;
* banco de dados;
* timezone;
* kiosk;
* câmera.

---

# ÚLTIMAS ALTERAÇÕES

### 2026-10-01

* Fase 0 concluída: criada a documentação de arquitetura.
* Arquivos: `ARCHITECTURE.md`, `DATABASE.md`, `API.md`, `SECURITY.md`, `BUSINESS-RULES.md`, `BIOMETRICS.md`, `TEST-PLAN.md`, `PROJECT-STATE.md`.
* Testes: não aplicável (sem código).
* Resultado: arquitetura definida; 4 decisões pendentes listadas.
* Revisão com as definições do responsável: perfis Administrador/Funcionário, kiosk só com escolha de batida,
  consulta do banco de horas pelo rosto, horário fixo no cadastro do funcionário; pontos de Portaria 671 e PIN descartados.
* Correção do responsável: o funcionário tem **horário fixo** (não carga horária solta), informado no cadastro.
* **Fase 1 concluída:** backend base (FastAPI + PostgreSQL + Alembic), login do administrador, administradores,
  funcionários com horário fixo, auditoria, Docker. 81 testes passando.
* Horário fixo passou a ser entrada/saída + duração do almoço (almoço livre). Migration `0002`.
* **Fase 2 concluída:** batidas, sequência, duplicidade, dia de jornada (inclui turno noturno), ajustes, histórico,
  motor de cálculo, feriados, banco de horas, terminais, configurações. Migration `0003`. 165 testes passando.
* Cadastro aceita dias por nome. **Fase 3 concluída:** auditoria consultável, resumo do banco de horas, limites de
  requisição, cabeçalhos de segurança, OpenAPI. A auditoria passou a usar o relógio do backend. 179 testes passando.
* Dia do pagamento e horas por ciclo de pagamento (`/pagamento`); migration `0004`. 200 testes no backend.
* **Fase 4 concluída:** painel web do administrador (React). Testes de navegador acharam e corrigiram: CSP
  descartada pelo nginx (`add_header` em `location`) e um teste instável (corrigido no teste).

Formato:

### [DATA]

* alteração;
* arquivos;
* testes;
* resultado.

---

# TESTES DA ÚLTIMA SESSÃO

**Comando:**
```
cd backend
TEST_DATABASE_URL=postgresql+psycopg://ponto:ponto@localhost:5433/ponto_test uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run alembic upgrade head / downgrade / upgrade / check   (0001 → 0003)

cd frontend
npm run lint && npm run typecheck && npm test && npm run build
E2E_DATABASE_URL=postgresql+psycopg://ponto:ponto@localhost:5433/ponto_e2e npm run e2e
```

**Resultado:**
Backend: 200 passed; ruff, mypy (strict). Frontend: eslint, tsc, 12 testes Vitest, build, 2 testes E2E
(Playwright/Chromium) estáveis em 6 execuções; E2E também contra nginx + build de produção.

**Falhas:**
Fase 4: nginx descartava os cabeçalhos de segurança (CSP) por causa de `add_header` dentro de `location`
(corrigido); teste E2E instável por não esperar a troca de página (corrigido no teste); classes `@apply` do
Tailwind 4 (corrigido).

---

# PRÓXIMA SESSÃO DO CLAUDE CODE

Ao iniciar uma nova sessão:

1. Ler `MASTER-PROMPT.md`.
2. Ler este arquivo.
3. Verificar a fase atual.
4. Verificar os arquivos existentes.
5. Continuar apenas a próxima etapa necessária.
6. Executar testes.
7. Atualizar este arquivo.
8. Informar resumidamente o que foi feito.

---

# LOG DE SESSÕES

## Sessão 1 — 2026-10-01

**Status:** Concluída.

* Lidos `MASTER-PROMPT.md` e `PROJECT-STATE.md`; repositório sem código.
* Executada a Fase 0 (documentação de arquitetura) e revisada com as definições do responsável.
* Executada a **Fase 1 — Backend base** (ver seção da fase).
* Definição do responsável: horário fixo = entrada e saída (ex.: 08:00–16:00), almoço livre com duração prevista
  (padrão 60 min). Migration `0002`.
* Executada a **Fase 2 — Registros e cálculo** (ver seção da fase).
* Definição do responsável: o administrador digita nome, dias de trabalho, horário fixo e tempo de almoço;
  trabalho em dia fora da escala é hora extra. A API passou a aceitar os dias por nome.
* Executada a **Fase 3 — API completa** (ver seção da fase).
* Executada a **Fase 4 — Frontend** (ver seção da fase).
* Próxima sessão: **Fase 5 — Biometria e Kiosk** (`BIOMETRICS.md`): confirmar licenças de YuNet/SFace; serviço
  `app/biometrics/` (detecção, qualidade, embedding, matching com limiar e margem); tabelas `biometric_consents` e
  `biometric_templates` com AES-256-GCM (`BIOMETRIC_KEY`); endpoints `/kiosk/identify`, `/kiosk/records`,
  `/kiosk/hour-bank` (token de identificação de 60 s) e de cadastro do rosto; tela `/kiosk` (câmera, MediaPipe para
  enquadramento, botões de batida, consulta do próprio banco de horas); cadastro do rosto em `/funcionarios/:id`;
  testes A11–A13 e §7 do `TEST-PLAN.md` (E2E com câmera simulada).

---

# CRITÉRIO DE CONCLUSÃO

O sistema estará concluído quando todas as fases estiverem marcadas como concluídas e os critérios definidos em `MASTER-PROMPT.md` forem atendidos.

# FIM
