# PROJECT-STATE.md

# Sistema de Ponto Eletrônico com Reconhecimento Facial

Este arquivo representa o estado atual do projeto.

Ele deve ser atualizado pelo Claude Code ao final de cada etapa significativa.

---

# STATUS GERAL

**Status:** EM ANDAMENTO

**Fase atual:** Fase 0 — Arquitetura (CONCLUÍDA) → próxima: Fase 1 — Backend base

**Última atualização:** 2026-10-01

**Último commit:** `docs: define phase 0 architecture` (branch `claude/oi-xu1bph`; ver `git log`)

**Próxima ação:** Revisar as decisões pendentes (seção DECISÕES PENDENTES) e iniciar a Fase 1.

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
* [x] `SECURITY.md` — ameaças, autenticação, kiosk, matriz RBAC, segredos, auditoria
* [x] `BUSINESS-RULES.md` — sequência, duplicidade, dia de jornada, motor de cálculo, tolerância, noturno, feriados, banco de horas
* [x] `BIOMETRICS.md` — comparação de alternativas, decisão, armazenamento, retenção, riscos
* [x] `TEST-PLAN.md` — estratégia e casos obrigatórios com exemplos numéricos (C01–C24, R01–R17, A01–A12)

### Testes

Não aplicável (fase apenas de documentação; nenhum código criado). Os exemplos numéricos do
`TEST-PLAN.md` foram conferidos manualmente (dias da semana de set/2026 e contas de minutos).

### Decisões

Ver seção DECISÕES TÉCNICAS.

---

# Fase 1 — Backend base

**Status:** PENDENTE

### Objetivos

* [ ] PostgreSQL
* [ ] Docker
* [ ] migrations
* [ ] modelos
* [ ] usuários
* [ ] autenticação
* [ ] autorização
* [ ] funcionários
* [ ] jornadas

### Testes

Pendente.

---

# Fase 2 — Registros e cálculo

**Status:** PENDENTE

### Objetivos

* [ ] registros ENTRY
* [ ] registros LUNCH_EXIT
* [ ] registros LUNCH_RETURN
* [ ] registros EXIT
* [ ] validação de sequência
* [ ] prevenção de duplicidade
* [ ] cálculo de jornada
* [ ] horas extras
* [ ] atrasos
* [ ] faltas
* [ ] banco de horas
* [ ] feriados
* [ ] finais de semana
* [ ] jornadas especiais

### Testes

Pendente.

---

# Fase 3 — API

**Status:** PENDENTE

### Objetivos

* [ ] autenticação
* [ ] funcionários
* [ ] jornadas
* [ ] registros
* [ ] histórico
* [ ] cálculos
* [ ] banco de horas
* [ ] usuários
* [ ] permissões
* [ ] auditoria
* [ ] feriados
* [ ] filtros
* [ ] paginação
* [ ] ordenação
* [ ] tratamento de erros
* [ ] OpenAPI
* [ ] testes de integração

---

# Fase 4 — Frontend

**Status:** PENDENTE

### Rotas

* [ ] `/login`
* [ ] `/kiosk`
* [ ] `/historico`
* [ ] `/banco-de-horas`
* [ ] `/funcionarios`
* [ ] `/jornadas`
* [ ] `/admin`

### Funcionalidades

* [ ] login
* [ ] gerenciamento de funcionários
* [ ] gerenciamento de jornadas
* [ ] histórico
* [ ] banco de horas
* [ ] administração

---

# Fase 5 — Biometria e Kiosk

**Status:** PENDENTE

### Objetivos

* [ ] decisão da tecnologia biométrica
* [ ] documentação
* [ ] câmera
* [ ] detecção facial
* [ ] identificação
* [ ] registro
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

**Decisão:** JWT de acesso (15 min, em memória) + refresh opaco rotacionado em cookie HttpOnly; kiosk com token de dispositivo; RBAC com perfis ADMIN, HR, MANAGER, EMPLOYEE. `SECURITY.md`.

---

# DECISÕES PENDENTES (precisam do responsável pelo projeto)

1. **Portaria MTP 671/2021 (REP-P):** o sistema precisa ser um REP-P conforme (comprovante, AFD/AEJ, atestado técnico)? Hoje está **fora do escopo**; a arquitetura não impede. `BUSINESS-RULES.md` §11.
2. **Alternativa à biometria** para quem não consentir: proposta de matrícula + PIN auditado. `BIOMETRICS.md` §4.
3. **Retenção** dos registros de ponto e da auditoria (prazo legal/contábil da empresa). `SECURITY.md` §8.
4. **Valores padrão** a confirmar: tolerância 5/10 min, intervalo mínimo entre marcações 2 min, `max_shift_hours` 16 h, prazo de banco de horas, feriado zerar escala 12x36.

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

* [ ] autenticação
* [ ] autorização
* [ ] proteção de rotas
* [ ] hash de senha
* [ ] expiração de sessão
* [ ] auditoria de login
* [ ] proteção de secrets
* [ ] proteção de biometria
* [ ] controle de acesso
* [ ] HTTPS
* [ ] revisão final

---

# TESTES

## Unitários

* [ ] jornada normal
* [ ] intervalo
* [ ] atraso
* [ ] saída antecipada
* [ ] hora extra
* [ ] falta
* [ ] duplicidade
* [ ] registro incompleto
* [ ] jornada noturna
* [ ] feriado
* [ ] final de semana
* [ ] banco de horas
* [ ] período inclusivo

## Integração

* [ ] autenticação
* [ ] funcionários
* [ ] jornadas
* [ ] registros
* [ ] cálculos
* [ ] histórico
* [ ] banco de horas
* [ ] auditoria

## Frontend

* [ ] login
* [ ] cadastro
* [ ] histórico
* [ ] banco de horas
* [ ] kiosk

---

# PROBLEMAS CONHECIDOS

Nenhum problema registrado.

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
| conformidade | Portaria 671/2021 não contemplada | Decisão pendente nº 1; não declarar conformidade |
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

Formato:

### [DATA]

* alteração;
* arquivos;
* testes;
* resultado.

---

# TESTES DA ÚLTIMA SESSÃO

**Comando:**
Nenhum (Fase 0 é só documentação).

**Resultado:**
Não aplicável.

**Falhas:**
Nenhuma.

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
* Executada a Fase 0 (documentação de arquitetura).
* Próxima sessão: resolver/confirmar as DECISÕES PENDENTES e iniciar a **Fase 1 — Backend base**
  (estrutura `backend/`, Docker Compose com PostgreSQL, Alembic, modelos da Fase 1 em `DATABASE.md` §3,
  autenticação/autorização, usuários, funcionários, jornadas e testes A01–A12 e seção 6 do `TEST-PLAN.md`).

---

# CRITÉRIO DE CONCLUSÃO

O sistema estará concluído quando todas as fases estiverem marcadas como concluídas e os critérios definidos em `MASTER-PROMPT.md` forem atendidos.

# FIM
