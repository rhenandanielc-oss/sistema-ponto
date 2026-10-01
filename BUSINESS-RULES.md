# BUSINESS-RULES.md

# Regras de Negócio — Sistema de Ponto

> **Status:** projetado na Fase 0 (revisado em 2026-10-01 com as definições do responsável).
> As regras abaixo são a especificação que as Fases 1 e 2 devem implementar.
> Valores marcados como **configurável** ficam em configuração da empresa (tabela `settings`), com o padrão indicado.

---

## 1. Conceitos

| Termo | Definição |
|---|---|
| **Administrador** | Único perfil com login e senha. Gerencia funcionários, horários, feriados, ajustes, dispositivos e relatórios. |
| **Funcionário** | Não tem login nem senha. É identificado **somente pelo rosto** no kiosk, onde registra o ponto e consulta o próprio banco de horas. |
| **Registro (batida)** | Um evento de ponto: `ENTRY`, `LUNCH_EXIT`, `LUNCH_RETURN` ou `EXIT`, com horário oficial do servidor. |
| **Dia de jornada (workday)** | A data (no fuso da empresa) à qual um conjunto de registros pertence. Para turno noturno, é a data da **entrada**. |
| **Horário fixo** | Horários de entrada, almoço e saída de cada dia da semana, informados no cadastro do funcionário. |
| **Carga planejada** | Minutos que o funcionário deveria trabalhar no dia, derivados do horário fixo. |
| **Minutos trabalhados** | Soma dos períodos efetivamente trabalhados (excluindo intervalo). |
| **Saldo diário** | `trabalhado − planejado`, após aplicação da tolerância. |
| **Banco de horas** | Saldo acumulado dos dias fechados + lançamentos manuais do administrador. |

---

## 2. Funcionários

* Cadastro feito pelo administrador. Campos: nome, matrícula (única), CPF (opcional, único), data de admissão,
  data de desligamento (opcional), situação (`ACTIVE`/`INACTIVE`) e **horário fixo** (§3).
* O cadastro biométrico (rosto) é feito pelo administrador junto com o funcionário (ver `BIOMETRICS.md`).
* **Desativação** não apaga dados: o funcionário deixa de ser reconhecido no kiosk e não registra ponto.
  Histórico e banco de horas continuam consultáveis pelo administrador.
* Dias anteriores à admissão ou posteriores ao desligamento têm carga planejada **zero**.
* Toda alteração cadastral gera auditoria com valores antes/depois (é o "histórico" do funcionário).

---

## 3. Horário fixo do funcionário

Cada funcionário tem um **horário fixo de trabalho**, informado pelo administrador **no cadastro do funcionário**
(junto com o nome e o rosto). O horário ainda não é conhecido hoje; por isso ele é um campo do cadastro, e não um
valor fixo no sistema.

Para cada dia da semana trabalhado, o horário define:

| Campo | Exemplo | Obrigatório |
|---|---|---|
| Entrada | 08:00 | sim |
| Saída para almoço | 12:00 | não (dia sem intervalo) |
| Retorno do almoço | 13:00 | sim, se houver saída para almoço |
| Saída | 17:00 | sim |

* Na tela de cadastro o administrador preenche o horário uma vez e marca os dias da semana trabalhados
  (padrão: segunda a sexta); se algum dia for diferente (ex.: sábado 08:00–12:00), ajusta só aquele dia.
* Dias não marcados são folga.
* **Carga planejada do dia** = `(saída − entrada) − (retorno do almoço − saída para almoço)`.
  Ex.: 08:00–12:00 / 13:00–17:00 ⇒ 480 min.
* Saída menor que a entrada ⇒ o turno termina no dia seguinte (turno noturno, ex.: 22:00–06:00).
  O intervalo precisa estar dentro do turno.

### 3.1 Vigência

* O horário tem **vigência** (`valid_from`, `valid_to` opcional). Ao alterar o horário, o administrador informa a
  partir de quando vale; o anterior é encerrado no dia anterior. Vigências não se sobrepõem.
* O cálculo de um dia usa o horário vigente **naquele dia** — alterar o horário hoje não muda o passado.
* A primeira vigência começa na data de admissão (obrigatória no cadastro).

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
   Exceção: se `t` cai até **4 horas antes** (configurável, `early_entry_window_hours`) da entrada de um turno
   previsto para o dia seguinte local (ex.: entrada às 23:50 para turno que começa 00:00), o dia de jornada é o do turno.
3. Um ciclo aberto há mais de `max_shift_hours` é considerado **incompleto**; a correção é por ajuste do administrador.

Exemplo: entrada 22:00 de 10/09 e saída 06:00 de 11/09 ⇒ ambos pertencem ao dia de jornada **10/09**.

### 4.5 Validações obrigatórias no backend

| Validação | Erro |
|---|---|
| Funcionário existe | `EMPLOYEE_NOT_FOUND` (404) |
| Funcionário ativo e dentro do período de admissão/desligamento | `EMPLOYEE_INACTIVE` (409) |
| Horário vigente | `NO_APPLICABLE_SCHEDULE` (409) |
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
| `day_type` | `WORKDAY`, `DAY_OFF` (dia não trabalhado no horário), `HOLIDAY`, `NOT_EMPLOYED` |
| `planned_minutes` | Carga do horário vigente naquele dia da semana; **0** em `DAY_OFF`, `HOLIDAY`, `NOT_EMPLOYED` |
| `worked_minutes` | `(LUNCH_EXIT − ENTRY) + (EXIT − LUNCH_RETURN)`, ou `EXIT − ENTRY` sem intervalo |
| `break_minutes` | `LUNCH_RETURN − LUNCH_EXIT` (0 se não houve intervalo) |
| `late_minutes` | `max(0, ENTRY − entrada prevista)` — atraso |
| `early_leave_minutes` | `max(0, saída prevista − EXIT)` — saída antecipada |
| `missing_minutes` | `max(0, −saldo)` — horas faltantes no dia |
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

## 6. Tolerância (CLT art. 58 §1º)

* Variações de até **5 minutos por batida**, com limite de **10 minutos no dia**, não são computadas
  (configuráveis: `tolerance_per_mark_minutes`, `tolerance_daily_minutes`).
* Regra (somente dias `WORKDAY` completos):
  1. Calcula-se o desvio absoluto de cada batida em relação ao horário previsto
     (entrada, saída para almoço, retorno do almoço, saída).
  2. Se **todo** desvio ≤ 5 min **e** a soma dos desvios ≤ 10 min ⇒ `balance=0`, `late=0`, `early_leave=0`,
     `overtime=0`, `missing=0`.
  3. Caso contrário, os minutos são computados **integralmente** (não se desconta a tolerância).

---

## 7. Trabalho noturno

* Período noturno: **22:00 às 05:00** no fuso da empresa (configurável).
* O motor informa `night_minutes` (reais) e `night_minutes_reduced` (`× 60 / 52,5`, hora noturna reduzida — CLT art. 73).
* O saldo e o banco de horas usam **minutos reais**; os minutos noturnos são informativos para a folha.
* Turno noturno conta no dia da **entrada** prevista (ex.: turno 22:00–06:00 de quinta conta na quinta).

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
