# PROJECT-STATE.md

# Sistema de Ponto Eletrônico com Reconhecimento Facial

Este arquivo representa o estado atual do projeto.

Ele deve ser atualizado pelo Claude Code ao final de cada etapa significativa.

---

# STATUS GERAL

**Status:** NÃO INICIADO

**Fase atual:** Fase 0 — Arquitetura

**Última atualização:** A preencher pelo Claude Code.

**Último commit:** A preencher.

**Próxima ação:** Criar e revisar a documentação arquitetural inicial.

---

# FASES

## Fase 0 — Arquitetura

**Status:** PENDENTE

### Objetivos

* definir arquitetura;
* definir banco;
* definir API;
* definir segurança;
* definir regras de negócio;
* definir arquitetura biométrica;
* definir estratégia de testes.

### Entregáveis

* [ ] `ARCHITECTURE.md`
* [ ] `DATABASE.md`
* [ ] `API.md`
* [ ] `SECURITY.md`
* [ ] `BUSINESS-RULES.md`
* [ ] `BIOMETRICS.md`
* [ ] `TEST-PLAN.md`

### Testes

Ainda não executados.

### Decisões

Ainda não definidas.

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

Nenhuma decisão registrada.

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

Nenhum risco registrado.

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

Nenhuma.

Formato:

### [DATA]

* alteração;
* arquivos;
* testes;
* resultado.

---

# TESTES DA ÚLTIMA SESSÃO

**Comando:**
A preencher.

**Resultado:**
A preencher.

**Falhas:**
A preencher.

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

## Sessão 1

**Status:** Não iniciada.

---

# CRITÉRIO DE CONCLUSÃO

O sistema estará concluído quando todas as fases estiverem marcadas como concluídas e os critérios definidos em `MASTER-PROMPT.md` forem atendidos.

# FIM
