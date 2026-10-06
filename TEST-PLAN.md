# TEST-PLAN.md

# Plano de Testes

> **Status:** Fases 1–5 implementadas. Backend: 230 testes (2 deles só com os modelos reais: `REAL_FACE_MODELS_DIR`).
> Frontend: Vitest (13) e Playwright E2E (3: administrador, login errado, terminal com câmera simulada).

---

## 1. Estratégia

| Nível | Ferramenta | Escopo | Fase |
|---|---|---|---|
| Unitário (backend) | pytest | Motor de cálculo (`app/calculation`), validação de sequência, atribuição de dia de jornada, tolerância, regras puras | 1–2 |
| Integração (backend) | pytest + FastAPI `TestClient` + **PostgreSQL real** em contêiner | Endpoints, autenticação, autorização, transações, restrições do banco, concorrência | 1–3 |
| Migrations | pytest | `alembic upgrade head` em banco vazio e `downgrade -1`/`upgrade` da última migration | 1+ |
| Frontend | Vitest + Testing Library | Cliente da API (renovação de sessão, erros), formatação, períodos, formulário de horário | 4 |
| E2E | Playwright | Login (certo e errado), cadastro com dias/horário/almoço, validação vinda do backend, inclusão e anulação de batidas, banco de horas, feriado, terminal, auditoria, sessão após recarregar e logout; também contra o build no nginx. Kiosk na Fase 5 (câmera simulada) | 4–5 |
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

## 7. Kiosk e biometria (Fase 5) — implementado em `tests/integration/test_kiosk_biometrics.py`, `tests/unit/test_biometrics.py`, `tests/unit/test_face_engine_real.py`, `frontend/e2e/kiosk.spec.ts`

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

---

## 9. Pagamento (BUSINESS-RULES.md §11)

| # | Caso | Esperado |
|---|---|---|
| P01 | Pagamento dia 5, data 01/09 | ciclo 06/08–05/09 |
| P02 | Dia do pagamento entra no ciclo | 05/09 → ciclo que termina em 05/09 |
| P03 | Dia 31 em fevereiro / abril | último dia do mês (28/02, 30/04); bissexto 29/02 |
| P04 | Virada de ano | pagamento dia 10: 11/12–10/01 |
| P05 | Ciclos consecutivos | cobrem todos os dias, sem sobreposição |
| P06 | Horas do ciclo | 8h + 9h30 + falta + 7h30 ⇒ 25,00 h trabalhadas; 1,50 h extras; 8,50 h faltantes |
| P07 | Dia incompleto no ciclo | contado em `incomplete_days` |
| P08 | Resumo | cada funcionário no seu próprio ciclo (dias 5 e 20) |
| P09 | Validação | `payday` obrigatório, 1–31; mês inválido ⇒ 422 |
| P10 | Horas a pagar | fixas + extras − faltantes: 32 + 1,5 − 8,5 = 25 h; variação dentro da tolerância não desconta (32 + 2 − 0 = 34 h) |


## 10. Produção e segurança (Fase 6)

| # | Caso | Onde | Esperado |
|---|---|---|---|
| S01 | Alterar/apagar auditoria, batidas, ajustes e lançamentos direto no banco | `test_immutable_history.py` | erro do banco; histórico intacto |
| S02 | Desanular batida anulada | `test_immutable_history.py` | erro do banco |
| S03 | Imagem "bomba" (PNG 20000 × 20000 em 400 KB) | `test_biometrics.py` | `INVALID_IMAGE`, sem alocar a imagem |
| S04 | Segredos fracos / cookie inseguro em produção | `test_biometrics.py` | aplicação não inicia |
| S05 | Documentação interativa em produção | `test_health_and_errors.py` | `/api/docs` e OpenAPI ⇒ 404 |
| S06 | Log de acesso | `test_health_and_errors.py` | JSON com `request_id`; sem query string e sem senha |
| S07 | Limpeza diária | `test_kiosk_biometrics.py`, `test_cli.py` | expurga templates excluídos há 30+ dias e identificações vencidas há 7+ dias; auditada |
| S08 | Pilha de produção (manual, 2026-10-01) | `docker-compose.prod.yml` | HTTPS + HSTS, HTTP → HTTPS, login, relatórios, kiosk sem erro de CSP, backup diário, restauração com `deploy/restore.sh`, `X-Forwarded-For` falso não burla o limite de login |
| S09 | Desempenho (manual) | `DEPLOY.md` §9 | 200 funcionários: relatórios em até ~1,6 s |
| S10 | Aviso de relógio do servidor diferente do aparelho | `src/kiosk/clock.test.ts` + manual | aviso acima de 2 min; nenhum aviso até 2 min |
| S11 | Modo de um computador só (manual, Linux equivalente) | `docker-compose.local.yml`, `windows/*.ps1` (PowerShell 7) | sistema só em `localhost`; sessão mantida com cookie seguro em `http://localhost`; câmera abre; backup em pasta com espaços; primeiro backup já com tabelas; restauração com `restaurar-backup.ps1` |

## 11. Folga semanal em qualquer dia (BUSINESS-RULES.md §3.2)

| # | Caso | Esperado |
|---|---|---|
| F01 | Horário 7 dias, sem batida na quinta | quinta = folga da semana; sem falta; semana com 6 × 8 h previstas |
| F02 | Sem batida no domingo | domingo = folga |
| F03 | Dois dias sem batida | o primeiro é folga, o segundo é falta |
| F04 | Trabalhou os 7 dias | domingo vira folga trabalhada: 8 h extras |
| F05 | Duas semanas (quinta e depois domingo) | uma folga por semana; saldo zero |
| F06 | Feriado na semana | não conta como a folga |
| F07 | Semana em andamento | dias passados mantêm a carga; domingo previsto como folga |
| F08 | Período começando no meio da semana | a folga já tirada antes do início continua valendo |
| F09 | Sem a opção | comportamento anterior (dia sem batida = falta) |

## 12. Consumo do funcionário (BUSINESS-RULES.md §12)

| # | Caso | Esperado |
|---|---|---|
| K01 | 2 refrigerantes de R$ 6,00 | lançamento de R$ 12,00 com a data de hoje |
| K02 | Preço do item muda | lançamentos antigos mantêm o preço da época |
| K03 | Consumo avulso (descrição + valor) | aceito |
| K04 | Cancelamento | sai do total; cancelar de novo ⇒ 409 |
| K05 | Consumo fora do ciclo | não entra no pagamento do ciclo |
| K06 | Pagamento e resumo | `consumption_cents` do ciclo de cada funcionário |
| K07 | Validação | nem item nem avulso, os dois, quantidade 0, preço 0, nome repetido, item desativado ⇒ erro |
| K08 | Terminal | o funcionário vê o próprio consumo do ciclo |
| K09 | Navegador (E2E) | item cadastrado em Administração → Consumo, lançado na ficha, total no ciclo |

## 13. Início do uso do sistema e zerar banco (BUSINESS-RULES.md §9.2 e §9.3)

| # | Caso | Esperado |
|---|---|---|
| Z01 | Admitido em 01/09, início do uso 06/10, sem batidas antes | nenhuma falta nem horas previstas antes de 06/10 |
| Z02 | Dia antes do início com batida | ignorado (sem extra) |
| Z03 | Pagamento dia 1 | ciclo 02/10–01/11; só conta a partir do início do uso |
| Z04 | Zerar banco com saldo negativo | lançamento de correção; saldo 0; dias seguintes voltam a contar |
| Z05 | Zerar com saldo zero | 409 |
| Z06 | Navegador (E2E) | botão "Zerar banco de horas" e configuração "Início do uso do sistema" |
