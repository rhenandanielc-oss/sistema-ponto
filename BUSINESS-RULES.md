# BUSINESS-RULES.md

# Regras de Negócio — Sistema de Ponto

> **Status:** projetado na Fase 0. As regras abaixo são a especificação que as Fases 1 e 2 devem implementar.
> Valores marcados como **configurável** ficam em configuração da empresa (tabela `settings`), com o padrão indicado.
> Este sistema **não substitui** a análise jurídica/contábil da empresa; ver §11 (conformidade).

---

## 1. Conceitos

| Termo | Definição |
|---|---|
| **Registro (marcação)** | Um evento de ponto: `ENTRY`, `LUNCH_EXIT`, `LUNCH_RETURN` ou `EXIT`, com horário oficial do servidor. |
| **Dia de jornada (workday)** | A data (no fuso da empresa) à qual um conjunto de registros pertence. Para jornada noturna, é a data da **entrada**. |
| **Jornada (work schedule)** | Modelo que define, por dia, horário de início, fim, intervalo e carga planejada. |
| **Carga planejada** | Minutos que o funcionário deveria trabalhar no dia. |
| **Minutos trabalhados** | Soma dos períodos efetivamente trabalhados (excluindo intervalo). |
| **Saldo diário** | `trabalhado − planejado`, após aplicação da tolerância. |
| **Banco de horas** | Saldo acumulado dos dias fechados + lançamentos manuais. |

---

## 2. Funcionários

* Campos mínimos: nome, matrícula (única), CPF (único, opcional na v1), e-mail opcional, data de admissão,
  data de desligamento opcional, situação (`ACTIVE`/`INACTIVE`), gestor responsável opcional.
* **Desativação** não apaga dados: o funcionário deixa de poder registrar ponto e de ser identificado
  pela biometria. Histórico e banco de horas permanecem consultáveis.
* Dias anteriores à admissão ou posteriores ao desligamento têm carga planejada **zero**.
* Toda alteração cadastral gera entrada de auditoria com valores antes/depois (é o "histórico" do funcionário).

---

## 3. Jornadas

### 3.1 Tipos

| Tipo | Descrição | Exemplo |
|---|---|---|
| `FIXED` | Horários fixos por dia da semana. Cada dia: início, fim, duração do intervalo (ou início/fim do intervalo). Dias sem definição são folga. | Seg–Sex 08:00–17:00, 1 h de almoço; Sáb 08:00–12:00 |
| `FLEXIBLE` | Apenas carga diária por dia da semana, sem horário de início. Não há cálculo de atraso/saída antecipada, apenas saldo. | Seg–Sex 8 h/dia |
| `ROTATING` | Escala cíclica de N dias a partir de uma data de referência; cada posição do ciclo é trabalho (com horários) ou folga. | 12x36: dia 1 trabalha 19:00–07:00, dia 2 folga |

Uma jornada pode atravessar a meia-noite (fim < início ⇒ termina no dia seguinte).

### 3.2 Associação ao funcionário

* O funcionário recebe jornada por **vigência** (`valid_from`, `valid_to` opcional). Vigências do mesmo
  funcionário não podem se sobrepor.
* O cálculo de um dia usa a jornada vigente **naquele dia** — trocar a jornada hoje não altera o passado.
* Funcionário ativo sem jornada vigente não pode registrar ponto (erro `NO_APPLICABLE_SCHEDULE`).

---

## 4. Registros de ponto

### 4.1 Horário oficial

* Definido pelo servidor (`now()` da transação). Qualquer horário enviado pelo cliente é ignorado.
* Registro guarda também: origem (`KIOSK`, `WEB`, `ADJUSTMENT`), dispositivo, usuário autor (se houver),
  método de identificação (`FACE`, `MANUAL`), score biométrico (se houver), IP.

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

* Na v1 há **um ciclo por dia de jornada** (uma entrada e uma saída). Múltiplos intervalos ficam fora do escopo
  e devem ser tratados por ajuste.
* Tipo fora da sequência ⇒ erro `INVALID_SEQUENCE` (inclui o próximo tipo esperado na resposta).

### 4.3 Duplicidade

* Um mesmo tipo não pode existir duas vezes no mesmo dia de jornada ⇒ `DUPLICATE_RECORD`
  (garantido também por restrição única no banco).
* **Intervalo mínimo entre marcações:** dois registros do mesmo funcionário com menos de
  **2 minutos** (configurável) de diferença são rejeitados ⇒ `DUPLICATE_RECORD`. Protege contra toque duplo no kiosk.

### 4.4 Atribuição ao dia de jornada (inclui jornada noturna)

Ao receber um registro no instante `t`:

1. Se existe um ciclo **aberto** (tem `ENTRY` e não tem `EXIT`) cujo `ENTRY` ocorreu há no máximo
   **16 horas** (configurável, `max_shift_hours`), o registro pertence a esse dia de jornada.
2. Caso contrário, só `ENTRY` é aceito, e o dia de jornada é a **data local de `t`**.
   Exceção: se `t` cai até **4 horas antes** (configurável, `early_entry_window_hours`) do início de um turno
   planejado para o dia seguinte local, o dia de jornada é o dia do turno.
3. Um ciclo aberto há mais de `max_shift_hours` é considerado **incompleto** e não aceita mais registros;
   a correção é por ajuste.

Exemplo: entrada 22:00 de 10/09 e saída 06:00 de 11/09 ⇒ ambos pertencem ao dia de jornada **10/09**.

### 4.5 Validações obrigatórias no backend

| Validação | Erro |
|---|---|
| Funcionário existe | `EMPLOYEE_NOT_FOUND` (404) |
| Funcionário ativo | `EMPLOYEE_INACTIVE` (409) |
| Jornada vigente | `NO_APPLICABLE_SCHEDULE` (409) |
| Sequência | `INVALID_SEQUENCE` (409) |
| Duplicidade | `DUPLICATE_RECORD` (409) |
| Dispositivo ativo e autorizado (kiosk) | `DEVICE_NOT_AUTHORIZED` (403) |
| Data dentro da admissão/desligamento | `EMPLOYEE_INACTIVE` (409) |

Todo registro aceito **e** toda tentativa rejeitada geram auditoria.

### 4.6 Imutabilidade e ajustes

* Registros nunca são editados nem excluídos fisicamente.
* Correções são feitas por **ajuste** (`time_record_adjustments`): incluir registro faltante ou anular
  um registro existente, sempre com justificativa, autor e data.
* Ajuste exige permissão `records:adjust`. Um usuário não pode ajustar os próprios registros.
* O registro anulado continua visível no histórico, marcado como anulado, com link para o ajuste.
* Registros incluídos por ajuste têm origem `ADJUSTMENT` e o horário informado pelo responsável
  (não o horário do servidor) — o horário de criação real fica no ajuste.

---

## 5. Motor de cálculo — resultado por dia

Para cada dia `d` do período consultado (**inclusivo** nas duas pontas), o motor produz:

| Campo | Regra |
|---|---|
| `day_type` | `WORKDAY`, `DAY_OFF` (folga/fim de semana sem jornada), `HOLIDAY`, `NOT_EMPLOYED` |
| `planned_minutes` | Carga da jornada vigente; **0** em `DAY_OFF`, `HOLIDAY`, `NOT_EMPLOYED` |
| `worked_minutes` | `(LUNCH_EXIT − ENTRY) + (EXIT − LUNCH_RETURN)`, ou `EXIT − ENTRY` sem intervalo |
| `break_minutes` | `LUNCH_RETURN − LUNCH_EXIT` (0 se não houve intervalo) |
| `late_minutes` | `max(0, ENTRY − início planejado)` — só `FIXED`/`ROTATING` |
| `early_leave_minutes` | `max(0, fim planejado − EXIT)` — só `FIXED`/`ROTATING` |
| `overtime_minutes` | `max(0, saldo)` |
| `night_minutes` | Minutos trabalhados entre 22:00 e 05:00 (ver §7) |
| `balance_minutes` | `worked − planned`, após tolerância (§6) |
| `status` | `OK`, `ABSENT`, `INCOMPLETE`, `INSUFFICIENT_BREAK` (pode acumular flags) |
| `counts_for_bank` | Se o saldo entra no banco de horas |

### 5.1 Casos especiais

* **Falta:** dia `WORKDAY` sem nenhum registro ⇒ `status=ABSENT`, `worked=0`, `balance=−planned`, entra no banco.
* **Registro incompleto:** falta `EXIT`, ou `LUNCH_EXIT` sem `LUNCH_RETURN`:
  `status=INCOMPLETE`, `worked` = soma apenas dos pares fechados, `counts_for_bank=false`
  até que um ajuste complete o dia. O dia corrente com ciclo aberto aparece como "em andamento", não incompleto.
* **Final de semana / folga trabalhada:** `planned=0`, todo minuto trabalhado é hora extra.
* **Feriado:** `planned=0`; trabalho no feriado é hora extra, marcada `holiday_work=true`.
* **Intervalo insuficiente:** se `worked > 6 h` e `break < 60 min`, ou `4 h < worked ≤ 6 h` e `break < 15 min`
  (CLT art. 71), marca `INSUFFICIENT_BREAK`. O sistema **sinaliza**; o pagamento do intervalo suprimido é
  tratamento de folha, fora do escopo.
* **Jornada `FLEXIBLE`:** sem atraso/saída antecipada; somente saldo.

---

## 6. Tolerância (CLT art. 58 §1º)

* Variações de até **5 minutos por marcação**, com limite de **10 minutos no dia**, não são computadas
  (configuráveis: `tolerance_per_mark_minutes`, `tolerance_daily_minutes`).
* Regra aplicada (somente `FIXED`/`ROTATING`, dias `WORKDAY` completos):
  1. Calcula-se o desvio absoluto de cada marcação em relação ao horário planejado
     (entrada, saída e, se a jornada definir horário fixo de intervalo, as marcações do intervalo).
  2. Se **todo** desvio ≤ 5 min **e** a soma dos desvios ≤ 10 min ⇒ `balance=0`, `late=0`, `early_leave=0`, `overtime=0`.
  3. Caso contrário, os minutos são computados **integralmente** (não se desconta a tolerância).
* Para `FLEXIBLE`, a tolerância diária se aplica ao saldo: `|balance| ≤ 10` ⇒ `balance=0`.

---

## 7. Trabalho noturno

* Período noturno: **22:00 às 05:00** no fuso da empresa (configurável).
* O motor informa `night_minutes` (minutos reais) e `night_minutes_reduced`
  (`night_minutes × 60 / 52,5`, hora noturna reduzida — CLT art. 73).
* **Decisão:** o saldo e o banco de horas usam **minutos reais**. Os minutos noturnos e a hora reduzida
  são informados para a folha (adicional noturno é tratamento de folha, fora do escopo).

---

## 8. Feriados

* Cadastro: data, nome, abrangência (`NATIONAL`, `STATE`, `MUNICIPAL`, `COMPANY`).
* Feriados recorrentes (mesmo dia/mês todo ano) podem ser marcados como `recurring`.
* Na v1 a empresa tem um único calendário (sem calendários por filial).
* Em feriado: carga planejada zero, mesmo que a jornada preveja trabalho naquele dia da semana.
* Jornada `ROTATING` (ex.: 12x36): **decisão padrão** — o feriado também zera a carga planejada;
  configurável por jornada (`holidays_apply=false` mantém a escala normal).

---

## 9. Banco de horas

* **Saldo acumulado em uma data `D`** = saldo inicial (abertura) + Σ `balance` dos dias com
  `counts_for_bank=true` até `D` + Σ lançamentos manuais até `D`.
* **Lançamentos manuais** (`hour_bank_entries`): crédito ou débito em minutos, com tipo
  (`OPENING_BALANCE`, `COMPENSATION`, `PAYOUT`, `CORRECTION`), justificativa e autor. Exigem `hour_bank:adjust`.
* A consulta por período (inclusivo) retorna: saldo anterior ao período, detalhamento diário,
  totais do período (planejado, trabalhado, extra, atraso, saldo) e saldo final.
* Prazo de compensação (CLT art. 59: 6 meses por acordo individual, 1 ano por acordo coletivo) é **configurável**
  (`hour_bank_expiration_months`). Na v1 o sistema **alerta** sobre saldos que estão vencendo; não zera automaticamente.

---

## 10. Períodos de consulta

* Sempre **inclusivos**: `01/09/2026 a 30/09/2026` inclui os dias 01 e 30.
* Atalhos:
  * **hoje:** data local atual;
  * **semana:** segunda a domingo da semana atual;
  * **mês:** dia 1 ao último dia do mês atual.
* Na API, `date_from` e `date_to` são datas (`YYYY-MM-DD`) interpretadas no fuso da empresa. Internamente,
  o filtro por instante é `[início do date_from, início do dia seguinte a date_to)`.
* Período máximo por consulta de cálculo: **366 dias** (proteção de performance).

---

## 11. Conformidade legal (pendente de decisão do responsável)

A Portaria MTP nº 671/2021 regula sistemas de registro eletrônico de ponto (REP-C, REP-A, REP-P).
Um sistema de ponto usado para controle oficial de jornada normalmente precisa atender a ela
(ex.: comprovante de registro ao trabalhador, arquivo AFD/AEJ, inalterabilidade dos registros, atestado técnico).

**O escopo atual do `MASTER-PROMPT.md` não inclui esses requisitos.** As decisões de arquitetura
(registros imutáveis, ajustes auditados, horário do servidor) foram tomadas para não impedir uma
adequação futura, mas **o sistema não deve ser declarado conforme à Portaria 671** sem uma fase específica
e validação jurídica. Registrado como risco em `PROJECT-STATE.md`.
