# TEST-PLAN.md

# Plano de Testes

> **Status:** Fases 1 e 2 implementadas — C01–C24, R01–R18, A01–A10 e §6 cobertos em `backend/tests/` (165 testes).
> A11–A13 e §7 dependem do kiosk (Fase 5).
> Cada fase registra os resultados em `PROJECT-STATE.md`.

---

## 1. Estratégia

| Nível | Ferramenta | Escopo | Fase |
|---|---|---|---|
| Unitário (backend) | pytest | Motor de cálculo (`app/calculation`), validação de sequência, atribuição de dia de jornada, tolerância, regras puras | 1–2 |
| Integração (backend) | pytest + FastAPI `TestClient` + **PostgreSQL real** em contêiner | Endpoints, autenticação, autorização, transações, restrições do banco, concorrência | 1–3 |
| Migrations | pytest | `alembic upgrade head` em banco vazio e `downgrade -1`/`upgrade` da última migration | 1+ |
| Frontend | Vitest + Testing Library | Componentes, formulários, tratamento de erros | 4 |
| E2E | Playwright | Login do administrador, cadastro, histórico, banco de horas, kiosk (batida e consulta do banco; câmera simulada com vídeo falso do Chromium) | 4–5 |
| Biometria | pytest + conjunto de imagens **sintéticas/autorizadas fora do repositório** | Detecção, qualidade, matching, limiar | 5 |

Regras:

* O motor de cálculo recebe tempo e dados como parâmetros ⇒ testes unitários **sem banco e sem relógio real**.
* Integração usa um banco descartável; nunca SQLite (as restrições `EXCLUDE`/índices parciais são do PostgreSQL).
* Nenhuma imagem facial real é versionada (o `.gitignore` já bloqueia as pastas usuais).
* Comando único: `docker compose --profile test run --rm tests` (sobe um PostgreSQL descartável).
  Localmente: `cd backend && TEST_DATABASE_URL=... uv run pytest`.
* Lint e tipagem (`ruff`, `mypy`, `tsc`) fazem parte da validação de cada fase.

---

## 2. Cenário-base dos exemplos

Salvo indicação, os exemplos usam:

* Fuso: `America/Sao_Paulo`.
* Funcionário **F1**: horário fixo de segunda a sexta — 08:00–17:00 com 60 min de almoço (livre)
  (**480 min** planejados); sábado e domingo folga.
* Tolerância: 5 min por batida, 10 min por dia.
* Datas em setembro de 2026 (01/09/2026 é terça-feira; 07/09/2026 é feriado nacional, segunda-feira).

---

## 3. Casos obrigatórios — motor de cálculo (unitários, Fase 2)

| # | Caso | Entrada | Resultado esperado |
|---|---|---|---|
| C01 | Jornada normal | F1, 01/09: ENTRY 08:00, LUNCH_EXIT 12:00, LUNCH_RETURN 13:00, EXIT 17:00 | worked 480, break 60, balance 0, status OK |
| C02 | Intervalo normal | Igual a C01 | break 60, sem `INSUFFICIENT_BREAK` |
| C03 | Intervalo insuficiente | 08:00 / 12:00 / 12:30 / 17:00 | worked 510, break 30, `INSUFFICIENT_BREAK`, balance +30 |
| C04 | Atraso | ENTRY 08:20, demais iguais a C01 | late 20, worked 460, missing 20, balance −20 |
| C05 | Dentro da tolerância | ENTRY 08:04, EXIT 17:03 | desvios 4 e 3 (cada ≤ 5, soma 7 ≤ 10) ⇒ late 0, balance 0 |
| C06 | Tolerância diária excedida | ENTRY 08:05, EXIT 16:54 | desvios 5 e 6 ⇒ computa tudo: late 5, early_leave 6, balance −11 |
| C05b | Almoço longo com entrada/saída pontuais | ENTRY 08:00, LUNCH_EXIT 12:00, LUNCH_RETURN 13:30, EXIT 17:00 | worked 450, balance −30 (tolerância não se aplica) |
| C05c | Almoço em qualquer horário | ENTRY 08:00, LUNCH_EXIT 10:15, LUNCH_RETURN 11:15, EXIT 17:00 | aceito; worked 480, balance 0 |
| C07 | Saída antecipada | EXIT 16:00 | early_leave 60, worked 420, balance −60 |
| C08 | Hora extra | EXIT 18:30 | worked 570, overtime 90, balance +90 |
| C09 | Falta | 02/09 (quarta) sem registros | ABSENT, worked 0, balance −480, entra no banco |
| C10 | Registro incompleto | 03/09: ENTRY 08:00, LUNCH_EXIT 12:00 | INCOMPLETE, worked 240, `counts_for_bank=false` |
| C11 | Horário diferente | F2: seg–sex 09:00–15:15 com 15 min de almoço (360 min); batidas 09:00 / 12:00 / 12:15 / 15:15 | planned 360, worked 360, break 15, balance 0 |
| C12 | Dias trabalhados diferentes | F3: horário de F1 + sábado 08:00–12:00 com almoço 0; 05/09 (sábado) sem registros | ABSENT, balance −240 |
| C13 | Final de semana trabalhado | F1, 05/09 (sábado) 08:00–12:00 | DAY_OFF, planned 0, overtime 240, balance +240 |
| C14 | Final de semana sem trabalho | F1, 06/09 (domingo) sem registros | DAY_OFF, balance 0, **não** é falta |
| C15 | Feriado sem trabalho | F1, 07/09 sem registros | HOLIDAY, planned 0, balance 0, não é falta |
| C16 | Feriado trabalhado | F1, 07/09 08:00–12:00 | overtime 240, `holiday_work=true` |
| C17 | Jornada atravessando a meia-noite | F4: seg–sex 22:00–06:00 com 60 min de almoço (420 min). ENTRY qui 10/09 22:00, LUNCH_EXIT 02:00, LUNCH_RETURN 03:00, EXIT sex 11/09 06:00 | workday_date 10/09, worked 420, balance 0, night_minutes 360, night_minutes_reduced ≈ 411 |
| C18 | Troca de horário | F1 até 15/09; a partir de 16/09: 09:00–16:00 com 60 min de almoço | 15/09 planned 480; 16/09 planned 360 e atraso medido a partir de 09:00 |
| C19 | Período de consulta inclusivo | 01/09/2026 a 30/09/2026 | **30** dias, primeiro 01/09, último 30/09 |
| C20 | Período de um dia | 01/09 a 01/09 | 1 dia |
| C21 | Banco de horas | OPENING_BALANCE +120; dias C04 (−20), C08 (+90), C10 (ignorado); COMPENSATION −60 | saldo final = 120 − 20 + 90 − 60 = **+130** |
| C22 | Banco — saldo anterior ao período | Consulta 10/09–20/09 com saldos antes de 10/09 | `opening_balance` soma tudo antes de 10/09 |
| C23 | Fora do contrato | Admissão 15/09; consulta 01/09–30/09 | 01/09–14/09 NOT_EMPLOYED, sem falta |
| C24 | Dia em andamento | Hoje com ENTRY e sem EXIT | IN_PROGRESS, fora do banco, não é INCOMPLETE |

---

## 4. Casos obrigatórios — regras de registro (unitários + integração, Fase 2)

| # | Caso | Esperado |
|---|---|---|
| R01 | Sequência completa (ENTRY → LUNCH_EXIT → LUNCH_RETURN → EXIT) | 4 registros |
| R02 | Sem intervalo (ENTRY → EXIT) | aceito |
| R03 | Primeiro registro do dia diferente de ENTRY | 409 `INVALID_SEQUENCE`, `expected=[ENTRY]` |
| R04 | LUNCH_RETURN sem LUNCH_EXIT | 409 `INVALID_SEQUENCE` |
| R05 | Registro após EXIT no mesmo dia de jornada | 409 `INVALID_SEQUENCE` |
| R06 | **Registro duplicado** — mesmo tipo duas vezes | 409 `DUPLICATE_RECORD` |
| R07 | Duas batidas com menos de 2 min | segunda: 409 `DUPLICATE_RECORD` |
| R08 | **Concorrência**: duas ENTRY simultâneas do mesmo funcionário | uma 201 e uma 409; um registro no banco |
| R09 | **Funcionário inativo** | 409 `EMPLOYEE_INACTIVE`, tentativa auditada |
| R10 | Funcionário inexistente (ajuste) | 404 `EMPLOYEE_NOT_FOUND` |
| R11 | Sem horário vigente | 409 `NO_APPLICABLE_SCHEDULE` |
| R12 | **Registro inválido**: tipo desconhecido; corpo com horário enviado pelo cliente | 422; horário do cliente ignorado |
| R13 | Saída de turno noturno após a meia-noite | EXIT 11/09 06:00 vinculado ao dia 10/09 |
| R14 | Ciclo aberto há mais de 16 h | não se vincula; só ENTRY aceito em novo dia |
| R15 | Dispositivo desativado | 403 `DEVICE_NOT_AUTHORIZED` |
| R16 | Ajuste sem justificativa | 422 |
| R17 | Ajuste VOID | registro marcado como anulado, não excluído; cálculo desconsidera; auditoria |
| R18 | Entrada antecipada para turno do dia seguinte | turno 00:00–08:00 de sexta; ENTRY qui 23:50 | dia de jornada = sexta |

---

## 5. Autenticação e acesso (integração, Fases 1 e 5)

| # | Caso | Esperado |
|---|---|---|
| A01 | Login válido do administrador | 200, access token, cookie de refresh `HttpOnly` |
| A02 | Senha errada / e-mail inexistente | 401 com a **mesma** mensagem |
| A03 | 5 falhas seguidas | 423 `ACCOUNT_LOCKED` por 15 min |
| A04 | Access token expirado | 401 `TOKEN_EXPIRED` |
| A05 | Refresh rotaciona; reuso do antigo | revoga a família |
| A06 | Logout | refresh revogado |
| A07 | Administrador desativado | não faz login nem refresh |
| A08 | Todo endpoint administrativo sem token | 401 (teste parametrizado sobre todas as rotas) |
| A09 | Token de dispositivo em endpoint administrativo | 401 |
| A10 | Desativar o último administrador ativo | 409 |
| A11 | Kiosk: banco de horas sem token de identificação / com token expirado | 401 `IDENTIFICATION_REQUIRED` |
| A12 | Kiosk: token de identificação do funcionário A | retorna **somente** dados de A (não há parâmetro de funcionário) |
| A13 | Kiosk: token de identificação reutilizado para uma segunda batida | 401 |

---

## 6. Funcionários e horário fixo (integração, Fase 1)

* Cadastro exige horário inicial (pelo menos um dia trabalhado).
* Validação do horário: turno de até 16 h; almoço ≥ 0 e menor que o turno; dias da semana sem repetição.
* Forma simples do cadastro (ex.: João 08:00–16:00) gera segunda a sexta com 60 min de almoço.
* Carga diária calculada: 08:00–16:00 (60) ⇒ 420; 08:00–17:00 (60) ⇒ 480; 22:00–06:00 (60) ⇒ 420; 08:00–12:00 (0) ⇒ 240.
* CRUD, pesquisa por nome/matrícula, paginação, ordenação.
* Matrícula e CPF duplicados ⇒ 409.
* Desativação mantém histórico.
* Histórico do funcionário reflete alterações (antes/depois).
* Novo horário com `valid_from` encerra o anterior em `valid_from − 1`; `valid_from` anterior ou igual ao início do vigente ⇒ 409 `SCHEDULE_OVERLAP`.

---

## 7. Kiosk e biometria (Fase 5)

* Identificação: 0 faces, 2 faces, baixa qualidade, não reconhecido, reconhecido.
* Funcionário inativo não é identificado.
* `identification_token` expirado ou reutilizado ⇒ rejeitado.
* Template de funcionário excluído deixa de ser considerado imediatamente.
* Imagens não são gravadas em disco (verificação de diretório temporário/logs).
* E2E com câmera falsa (`--use-fake-device-for-media-stream`), incluindo câmera indisponível e queda de rede.

---

## 8. Critérios de aceite por fase

* Todos os testes da fase passando.
* Testes de fases anteriores continuam passando.
* `ruff`, `mypy` (backend) e `tsc`/lint (frontend) sem erros.
* Resultado registrado em `PROJECT-STATE.md` (comando, resultado, falhas).
