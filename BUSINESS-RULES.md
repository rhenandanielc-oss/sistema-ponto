# BUSINESS-RULES.md

# Regras de Negócio — Sistema de Ponto

> **Status:** projetado na Fase 0 (revisado em 2026-10-01 com as definições do responsável).
> As regras abaixo são a especificação que as Fases 1 e 2 devem implementar.
> Valores marcados como **configurável** ficam em configuração da empresa (tabela `settings`), com o padrão indicado.

---

## 1. Conceitos

| Termo | Definição |
|---|---|
| **Administrador** | Único perfil com login e senha. Gerencia funcionários, cargas horárias, feriados, ajustes, dispositivos e relatórios. |
| **Funcionário** | Não tem login nem senha. É identificado **somente pelo rosto** no kiosk, onde registra o ponto e consulta o próprio banco de horas. |
| **Registro (batida)** | Um evento de ponto: `ENTRY`, `LUNCH_EXIT`, `LUNCH_RETURN` ou `EXIT`, com horário oficial do servidor. |
| **Dia de jornada (workday)** | A data (no fuso da empresa) à qual um conjunto de registros pertence. Para turno noturno, é a data da **entrada**. |
| **Carga horária** | Minutos que o funcionário deve trabalhar em cada dia da semana, informados no cadastro. |
| **Minutos trabalhados** | Soma dos períodos efetivamente trabalhados (excluindo intervalo). |
| **Saldo diário** | `trabalhado − planejado`, após aplicação da tolerância. |
| **Banco de horas** | Saldo acumulado dos dias fechados + lançamentos manuais do administrador. |

---

## 2. Funcionários

* Cadastro feito pelo administrador. Campos: nome, matrícula (única), CPF (opcional, único), data de admissão,
  data de desligamento (opcional), situação (`ACTIVE`/`INACTIVE`) e **carga horária** (§3).
* O cadastro biométrico (rosto) é feito pelo administrador junto com o funcionário (ver `BIOMETRICS.md`).
* **Desativação** não apaga dados: o funcionário deixa de ser reconhecido no kiosk e não registra ponto.
  Histórico e banco de horas continuam consultáveis pelo administrador.
* Dias anteriores à admissão ou posteriores ao desligamento têm carga planejada **zero**.
* Toda alteração cadastral gera auditoria com valores antes/depois (é o "histórico" do funcionário).

---

## 3. Carga horária

O responsável ainda não conhece os horários de cada funcionário; por isso o sistema **não exige horário de
entrada/saída**. Cada funcionário tem apenas:

* **carga diária** (ex.: 8 h = 480 min);
* **dias da semana trabalhados** (padrão: segunda a sexta).

Na tela de cadastro o administrador informa uma carga diária e marca os dias trabalhados; o sistema grava a
carga por dia da semana, o que permite, se necessário, um valor diferente em algum dia (ex.: sábado com 4 h).
Dias não marcados são folga.

### 3.1 Vigência

* A carga horária tem **vigência** (`valid_from`, `valid_to` opcional). Ao alterar a carga, o administrador
  informa a partir de quando vale; a anterior é encerrada no dia anterior. Vigências não se sobrepõem.
* O cálculo de um dia usa a carga vigente **naquele dia** — alterar a carga hoje não muda o passado.
* A primeira vigência começa na data de admissão (obrigatória no cadastro).

### 3.2 Consequências de não haver horário fixo

* **Atraso** e **saída antecipada** não são calculados separadamente (não há horário de referência).
  Eles aparecem como **horas faltantes** do dia (`missing_minutes`), reduzindo o saldo.
* A tolerância é aplicada sobre o saldo do dia (§6).
* Se no futuro horários fixos forem necessários, o modelo pode ser estendido sem perder dados.

---

## 4. Registros de ponto

### 4.1 Horário oficial e origem

* Definido pelo servidor (`now()` da transação). O kiosk não envia horário.
* O registro normal acontece **apenas no kiosk**, após reconhecimento facial. O funcionário só escolhe o tipo de batida.
* Cada registro guarda: origem (`KIOSK` ou `ADJUSTMENT`), dispositivo, método (`FACE`), score biométrico, IP.

### 4.2 Sequência válida dentro de um dia de jornada

```
(início) ──ENTRY──▶ TRABALHANDO ──LUNCH_EXIT──▶ EM_INTERVALO ──LUNCH_RETURN──▶ TRABALHANDO_2 ──EXIT──▶ (fechado)
                         │
                         └──────────────EXIT─────────────────▶ (fechado, sem intervalo)
```

| Estado atual | Próximos tipos permitidos |
|---|---|
| sem registros | `ENTRY` |
| `ENTRY` | `LUNCH_EXIT`, `EXIT` |
| `LUNCH_EXIT` | `LUNCH_RETURN` |
| `LUNCH_RETURN` | `EXIT` |
| `EXIT` | nenhum (dia fechado) |

* O kiosk mostra os quatro botões, habilitando apenas os tipos permitidos no momento.
* Um ciclo por dia de jornada na v1.
* Tipo fora da sequência ⇒ erro `INVALID_SEQUENCE`.

### 4.3 Duplicidade

* Um mesmo tipo não pode existir duas vezes no mesmo dia de jornada ⇒ `DUPLICATE_RECORD`
  (garantido também por restrição única no banco).
* Dois registros do mesmo funcionário com menos de **2 minutos** (configurável) de diferença ⇒ `DUPLICATE_RECORD`.

### 4.4 Atribuição ao dia de jornada (inclui turno noturno)

Ao receber um registro no instante `t`:

1. Se existe um ciclo **aberto** (tem `ENTRY` e não tem `EXIT`) cujo `ENTRY` ocorreu há no máximo
   **16 horas** (configurável, `max_shift_hours`), o registro pertence a esse dia de jornada.
2. Caso contrário, só `ENTRY` é aceito, e o dia de jornada é a **data local de `t`**.
3. Um ciclo aberto há mais de `max_shift_hours` é considerado **incompleto**; a correção é por ajuste do administrador.

Exemplo: entrada 22:00 de 10/09 e saída 06:00 de 11/09 ⇒ ambos pertencem ao dia de jornada **10/09**.

### 4.5 Validações obrigatórias no backend

| Validação | Erro |
|---|---|
| Funcionário existe | `EMPLOYEE_NOT_FOUND` (404) |
| Funcionário ativo e dentro do período de admissão/desligamento | `EMPLOYEE_INACTIVE` (409) |
| Carga horária vigente | `NO_APPLICABLE_WORKLOAD` (409) |
| Funcionário identificado pelo servidor (token de identificação válido) | `IDENTIFICATION_REQUIRED` (401) |
| Sequência | `INVALID_SEQUENCE` (409) |
| Duplicidade | `DUPLICATE_RECORD` (409) |
| Dispositivo ativo | `DEVICE_NOT_AUTHORIZED` (403) |

Todo registro aceito **e** toda tentativa rejeitada geram auditoria.

### 4.6 Imutabilidade e ajustes

* Registros nunca são editados nem excluídos fisicamente.
* Correções são feitas pelo **administrador** por **ajuste**: incluir registro faltante (ex.: esqueceu de bater a saída)
  ou anular um registro existente, sempre com justificativa.
* O registro anulado continua visível no histórico, marcado como anulado.
* Registros incluídos por ajuste têm origem `ADJUSTMENT` e o horário informado pelo administrador;
  o horário real da inclusão fica no ajuste.

---

## 5. Motor de cálculo — resultado por dia

Para cada dia `d` do período consultado (**inclusivo** nas duas pontas):

| Campo | Regra |
|---|---|
| `day_type` | `WORKDAY`, `DAY_OFF` (dia não trabalhado na carga), `HOLIDAY`, `NOT_EMPLOYED` |
| `planned_minutes` | Carga vigente daquele dia da semana; **0** em `DAY_OFF`, `HOLIDAY`, `NOT_EMPLOYED` |
| `worked_minutes` | `(LUNCH_EXIT − ENTRY) + (EXIT − LUNCH_RETURN)`, ou `EXIT − ENTRY` sem intervalo |
| `break_minutes` | `LUNCH_RETURN − LUNCH_EXIT` (0 se não houve intervalo) |
| `missing_minutes` | `max(0, −saldo)` — horas faltantes (cobre atraso e saída antecipada) |
| `overtime_minutes` | `max(0, saldo)` — horas extras |
| `night_minutes` | Minutos trabalhados entre 22:00 e 05:00 (§7) |
| `balance_minutes` | `worked − planned`, após tolerância (§6) |
| `status` | `OK`, `ABSENT`, `INCOMPLETE`, `INSUFFICIENT_BREAK`, `IN_PROGRESS` |
| `counts_for_bank` | Se o saldo entra no banco de horas |

### 5.1 Casos especiais

* **Falta:** dia `WORKDAY` passado sem nenhum registro ⇒ `ABSENT`, `worked=0`, `balance=−planned`, entra no banco.
* **Registro incompleto:** falta `EXIT`, ou `LUNCH_EXIT` sem `LUNCH_RETURN` ⇒ `INCOMPLETE`;
  `worked` soma só os pares fechados; `counts_for_bank=false` até o administrador completar por ajuste.
* **Dia em andamento:** o dia de hoje (ou turno aberto dentro de `max_shift_hours`) ⇒ `IN_PROGRESS`, fora do banco.
* **Folga trabalhada / fim de semana:** `planned=0`, todo minuto trabalhado é hora extra.
* **Feriado:** `planned=0`; trabalho no feriado é hora extra, marcado `holiday_work=true`.
* **Intervalo insuficiente:** `worked > 6 h` e `break < 60 min`, ou `4 h < worked ≤ 6 h` e `break < 15 min`
  (CLT art. 71) ⇒ sinaliza `INSUFFICIENT_BREAK`. O saldo continua sendo o tempo real trabalhado.

---

## 6. Tolerância

* Como não há horário fixo, a tolerância é aplicada ao **saldo diário**: se `|balance| ≤ 10 min`
  (configurável, `tolerance_daily_minutes`) ⇒ `balance = 0`.
* Acima do limite, o saldo é computado **integralmente** (não se desconta a tolerância) — mesmo critério do
  CLT art. 58 §1º.
* Aplica-se somente a dias `WORKDAY` completos.

---

## 7. Trabalho noturno

* Período noturno: **22:00 às 05:00** no fuso da empresa (configurável).
* O motor informa `night_minutes` (reais) e `night_minutes_reduced` (`× 60 / 52,5`, hora noturna reduzida — CLT art. 73).
* O saldo e o banco de horas usam **minutos reais**; os minutos noturnos são informativos para a folha.
* Turno noturno conta no dia da **entrada**: o dia da semana da entrada precisa estar marcado como dia trabalhado
  na carga do funcionário.

---

## 8. Feriados

* Cadastrados pelo administrador: data, nome, `recurring` (repete todo ano no mesmo dia/mês).
* Um único calendário para a empresa.
* Em feriado a carga planejada é zero.

---

## 9. Banco de horas

* **Saldo acumulado em uma data `D`** = Σ `balance` dos dias com `counts_for_bank=true` até `D`
  + Σ lançamentos manuais até `D`.
* **Lançamentos manuais** (somente administrador): crédito ou débito em minutos, com tipo
  (`OPENING_BALANCE`, `COMPENSATION`, `PAYOUT`, `CORRECTION`) e justificativa. Ex.: saldo trazido de controle anterior.
* Consulta por período (inclusivo): saldo anterior ao período, detalhamento diário, totais (planejado,
  trabalhado, extras, faltantes, saldo) e saldo final.

### 9.1 Consulta pelo funcionário (kiosk)

* O funcionário consulta o **próprio** banco de horas no kiosk, identificado pelo rosto (sem senha).
* O servidor só devolve dados do funcionário reconhecido — o kiosk não informa de quem é o banco.
* Mostra: saldo acumulado até hoje, horas extras e faltantes do mês atual e o detalhamento diário do mês.
* A tela fecha sozinha após **30 segundos** (configurável) ou ao tocar em "Sair".
* Cada consulta é auditada.

---

## 10. Períodos de consulta

* Sempre **inclusivos**: `01/09/2026 a 30/09/2026` inclui os dias 01 e 30.
* Atalhos: **hoje**; **semana** (segunda a domingo); **mês** (dia 1 ao último dia).
* Na API, `date_from`/`date_to` são datas no fuso da empresa; internamente o filtro é
  `[início de date_from, início do dia seguinte a date_to)`.
* Período máximo por consulta de cálculo: **366 dias**.
