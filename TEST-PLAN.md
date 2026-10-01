# TEST-PLAN.md

# Plano de Testes

> **Status:** planejado na Fase 0. Nenhum teste existe ainda. Cada fase deve implementar os testes
> listados para ela e registrar os resultados em `PROJECT-STATE.md`.

---

## 1. Estratégia

| Nível | Ferramenta | Escopo | Fase |
|---|---|---|---|
| Unitário (backend) | pytest | Motor de cálculo (`app/calculation`), validação de sequência, atribuição de dia de jornada, tolerância, regras puras | 1–2 |
| Integração (backend) | pytest + FastAPI `TestClient` + **PostgreSQL real** em contêiner | Endpoints, autenticação, autorização, transações, restrições do banco, concorrência | 1–3 |
| Migrations | pytest | `alembic upgrade head` em banco vazio e `downgrade -1`/`upgrade` da última migration | 1+ |
| Frontend | Vitest + Testing Library | Componentes, formulários, tratamento de erros | 4 |
| E2E | Playwright | Login, cadastro, histórico, banco de horas, kiosk (câmera simulada com vídeo falso do Chromium) | 4–5 |
| Biometria | pytest + conjunto de imagens **sintéticas/autorizadas fora do repositório** | Detecção, qualidade, matching, limiar | 5 |

Regras:

* O motor de cálculo recebe tempo e dados como parâmetros ⇒ testes unitários **sem banco e sem relógio real**.
* Integração usa um banco descartável; nunca SQLite (as restrições `EXCLUDE`/índices parciais são do PostgreSQL).
* Nenhuma imagem facial real é versionada (o `.gitignore` já bloqueia as pastas usuais).
* Testes devem rodar com um único comando (`docker compose run --rm backend pytest` — definido na Fase 1).
* Lint e tipagem (`ruff`, `mypy`, `tsc`) fazem parte da validação de cada fase.

---

## 2. Cenário-base dos exemplos

Salvo indicação, os exemplos usam:

* Fuso: `America/Sao_Paulo`.
* Jornada **J1 (`FIXED`)**: segunda a sexta, 08:00–17:00, intervalo de 60 min ⇒ **480 min** planejados; sábado e domingo folga.
* Tolerância: 5 min por marcação, 10 min por dia.
* Datas em setembro de 2026 (01/09/2026 é terça-feira; 07/09/2026 é feriado nacional, segunda-feira).

---

## 3. Casos obrigatórios — motor de cálculo (unitários, Fase 2)

| # | Caso | Entrada | Resultado esperado |
|---|---|---|---|
| C01 | Jornada normal | 01/09: ENTRY 08:00, LUNCH_EXIT 12:00, LUNCH_RETURN 13:00, EXIT 17:00 | worked 480, break 60, balance 0, status OK |
| C02 | Intervalo normal | Igual a C01 | break 60, sem `INSUFFICIENT_BREAK` |
| C03 | Intervalo insuficiente | 08:00 / 12:00 / 12:30 / 17:00 | worked 510, break 30, status `INSUFFICIENT_BREAK`, balance +30 |
| C04 | Atraso | ENTRY 08:20, demais iguais a C01 | late 20, worked 460, balance −20 |
| C05 | Atraso dentro da tolerância | ENTRY 08:04, EXIT 17:03 | desvios 4 e 3 (≤5, soma 7 ≤10) ⇒ balance 0, late 0 |
| C06 | Tolerância diária excedida | ENTRY 08:05 (tolerado isolado), EXIT 16:54 | desvios 5 e 6 ⇒ computa tudo: late 5, early_leave 6, balance −11 |
| C07 | Saída antecipada | EXIT 16:00 | early_leave 60, balance −60 |
| C08 | Hora extra | EXIT 18:30 | overtime 90, balance +90 |
| C09 | Falta | 02/09 (quarta) sem registros | status ABSENT, worked 0, balance −480, entra no banco |
| C10 | Registro incompleto | 03/09: ENTRY 08:00, LUNCH_EXIT 12:00 (sem retorno) | status INCOMPLETE, worked 240, `counts_for_bank=false` |
| C11 | Jornada diferente | J2 (`FIXED`) seg–sex 09:00–15:00 com 15 min de intervalo (345 min); registros 09:00/12:00/12:15/15:00 | planned 345, worked 345, balance 0 |
| C12 | Jornada flexível | J3 (`FLEXIBLE`) 480 min; ENTRY 10:00, EXIT 19:00, intervalo 60 | late não calculado, worked 480, balance 0 |
| C13 | Final de semana trabalhado | 05/09 (sábado) 08:00–12:00 com J1 | day_type DAY_OFF, planned 0, overtime 240, balance +240 |
| C14 | Final de semana sem trabalho | 06/09 (domingo) sem registros | DAY_OFF, balance 0, **não** é falta |
| C15 | Feriado sem trabalho | 07/09 sem registros | HOLIDAY, planned 0, balance 0, não é falta |
| C16 | Feriado trabalhado | 07/09 08:00–12:00 | overtime 240, `holiday_work=true` |
| C17 | Jornada atravessando a meia-noite | J4 (`FIXED`) 22:00–06:00, intervalo 60 (420 min). ENTRY 10/09 22:00, LUNCH_EXIT 02:00, LUNCH_RETURN 03:00, EXIT 11/09 06:00 | workday_date 10/09, worked 420, balance 0, night_minutes 360 (22:00–02:00 + 03:00–05:00), night_minutes_reduced ≈ 411 |
| C18 | 12x36 | J5 (`ROTATING`, ciclo 2, referência 01/09) 07:00–19:00, 60 min intervalo (660 min) | 01/09 e 03/09 dias de trabalho; 02/09 folga (não é falta) |
| C19 | Período de consulta inclusivo | Consulta 01/09/2026 a 30/09/2026 | retorna **30** dias, primeiro 01/09, último 30/09 |
| C20 | Período de um dia | 01/09 a 01/09 | retorna 1 dia |
| C21 | Banco de horas | Saldo de abertura +120; C04 (−20), C08 (+90), C10 (incompleto, ignorado), lançamento COMPENSATION −60 | saldo final = 120 − 20 + 90 − 60 = **+130** |
| C22 | Banco — saldo anterior ao período | Consulta 10/09–20/09 com dias anteriores com saldo | `opening_balance` considera tudo antes de 10/09 |
| C23 | Fora da vigência do contrato | Admissão em 15/09; consulta 01/09–30/09 | 01/09–14/09 NOT_EMPLOYED, sem falta |
| C24 | Troca de jornada | J1 até 15/09, J2 a partir de 16/09 | cada dia usa a jornada vigente |

---

## 4. Casos obrigatórios — regras de registro (unitários + integração, Fase 2)

| # | Caso | Esperado |
|---|---|---|
| R01 | Sequência válida completa (ENTRY → LUNCH_EXIT → LUNCH_RETURN → EXIT) | 4 registros criados |
| R02 | Sequência sem intervalo (ENTRY → EXIT) | aceito |
| R03 | Primeiro registro do dia diferente de ENTRY | 409 `INVALID_SEQUENCE`, `expected=[ENTRY]` |
| R04 | LUNCH_RETURN sem LUNCH_EXIT | 409 `INVALID_SEQUENCE` |
| R05 | Registro após EXIT no mesmo dia de jornada | 409 `INVALID_SEQUENCE` |
| R06 | **Registro duplicado** — mesmo tipo duas vezes | 409 `DUPLICATE_RECORD` |
| R07 | Duas marcações com menos de 2 min | segunda: 409 `DUPLICATE_RECORD` |
| R08 | **Concorrência**: duas requisições ENTRY simultâneas do mesmo funcionário | exatamente uma 201 e uma 409; um único registro no banco |
| R09 | **Funcionário inativo** | 409 `EMPLOYEE_INACTIVE`, tentativa auditada |
| R10 | Funcionário inexistente | 404 `EMPLOYEE_NOT_FOUND` |
| R11 | Sem jornada vigente | 409 `NO_APPLICABLE_SCHEDULE` |
| R12 | **Registro inválido**: tipo desconhecido, corpo com `recorded_at` enviado pelo cliente | 422 para tipo inválido; campo de horário ignorado — `recorded_at` é o do servidor |
| R13 | Saída de turno noturno após a meia-noite | EXIT em 11/09 06:00 vinculado ao dia de jornada 10/09 |
| R14 | Ciclo aberto há mais de 16 h | novo registro não se vincula; só ENTRY aceito em novo dia |
| R15 | Dispositivo desativado | 403 `DEVICE_NOT_AUTHORIZED` |
| R16 | Ajuste ADD sem justificativa / pelo próprio funcionário | 422 / 403 |
| R17 | Ajuste VOID | registro marcado como anulado, não excluído; cálculo desconsidera; auditoria criada |

---

## 5. Autenticação e autorização (integração, Fase 1)

| # | Caso | Esperado |
|---|---|---|
| A01 | Login válido | 200, access token, cookie de refresh `HttpOnly` |
| A02 | Senha errada / e-mail inexistente | 401 com a **mesma** mensagem |
| A03 | 5 falhas seguidas | 423 `ACCOUNT_LOCKED` por 15 min |
| A04 | Access token expirado | 401 `TOKEN_EXPIRED` |
| A05 | Refresh rotaciona; reuso do refresh antigo | revoga a família; próximo refresh falha |
| A06 | Logout | refresh revogado |
| A07 | Usuário desativado | não faz login nem refresh |
| A08 | Cada endpoint administrativo sem token | 401 |
| A09 | Matriz de permissões (`SECURITY.md` §4) | teste parametrizado por perfil × endpoint |
| A10 | MANAGER acessando funcionário fora do escopo | 404 |
| A11 | EMPLOYEE acessando dados de outro funcionário | 404 |
| A12 | Token de dispositivo em endpoint não-kiosk | 401/403 |

---

## 6. Funcionários e jornadas (integração, Fase 1)

* CRUD, pesquisa por nome/matrícula, paginação, ordenação.
* Matrícula e CPF duplicados ⇒ 409.
* Desativação mantém histórico.
* Histórico do funcionário reflete alterações (auditoria antes/depois).
* Vigências de jornada sobrepostas ⇒ 409 `SCHEDULE_OVERLAP`.
* Validação de dias da jornada (carga coerente com horários, turno noturno aceito).

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
