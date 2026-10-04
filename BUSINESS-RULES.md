# BUSINESS-RULES.md

# Regras de Negócio — Sistema de Ponto

> **Status:** §2–§10 **implementados** nas Fases 1 e 2 (`backend/app/calculation/`, `backend/app/services/`),
> exceto a consulta pelo kiosk (§9.1, Fase 5). Revisado em 2026-10-01 com as definições do responsável.
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

Exemplo do cadastro: **Nome:** João — **Dias:** segunda a sexta — **Horário fixo:** 08:00 – 16:00 — **Almoço:** 60 min.

Para cada dia da semana trabalhado, o horário define:

| Campo | Exemplo | Obrigatório |
|---|---|---|
| Entrada | 08:00 | sim |
| Saída | 16:00 | sim |
| Duração do almoço | 60 min | não — padrão **60 min**; pode ser 0 |

* **O almoço é livre** (decisão do responsável, 2026-10-01): o funcionário sai e volta do almoço quando quiser.
  O sistema não guarda horário de almoço nem recusa almoço "fora de hora"; só usa a **duração prevista**
  para calcular a carga do dia.
* Na tela de cadastro o administrador digita o horário uma vez e marca os dias da semana trabalhados
  (padrão: segunda a sexta); se algum dia for diferente (ex.: sábado 08:00–12:00 sem almoço), ajusta só aquele dia.
* O administrador digita os **dias de trabalho** pelo nome ("segunda", "terça-feira", "sáb"…) ou número
  (0 = segunda … 6 = domingo). Dias não informados são folga.
* **Trabalho em dia fora da escala conta inteiro como hora extra** (ex.: funcionário de segunda a sexta que trabalha
  no sábado — `DAY_OFF_WORK`, §5.1).
* **Carga planejada do dia** = `(saída − entrada) − duração do almoço`.
  Ex.: João, 08:00–16:00 com 60 min de almoço ⇒ **420 min (7 h)**.
* O almoço real é medido pelas batidas (`LUNCH_RETURN − LUNCH_EXIT`): quem almoça menos que o previsto trabalha
  mais e acumula hora extra; quem almoça mais acumula horas faltantes.
* Saída menor ou igual à entrada ⇒ o turno termina no dia seguinte (turno noturno, ex.: 22:00–06:00).
  Turno de até 16 h; almoço menor que o turno.

### 3.1 Vigência

* O horário tem **vigência** (`valid_from`, `valid_to` opcional). Ao alterar o horário, o administrador informa a
  partir de quando vale; o anterior é encerrado no dia anterior. Vigências não se sobrepõem.
* O cálculo de um dia usa o horário vigente **naquele dia** — alterar o horário hoje não muda o passado.
* A primeira vigência começa na data de admissão (obrigatória no cadastro).

### 3.2 Folga semanal em qualquer dia (decisão do responsável, 2026-10-04)

Para quem folga **um dia por semana, em dia variável** (ex.: numa semana na quinta, na outra no domingo), o horário
tem a opção **"Folga semanal em qualquer dia"** (`weekly_day_off`). Nesse caso os dias marcados no horário são os
dias em que ele **pode** trabalhar (normalmente todos os 7), e em cada semana — **segunda a domingo** — o sistema
escolhe a folga sozinho:

1. a folga é o **primeiro dia de trabalho da semana sem nenhuma batida** (o dia não conta como falta nem tem horas
   previstas);
2. outro dia sem batida na mesma semana é **falta** normal;
3. se ele não folgou até o **último dia de trabalho da semana**, esse último dia é a folga: trabalhando nele, todo o
   tempo é **hora extra** (`DAY_OFF_WORK`). Assim a carga da semana é sempre de 6 dias (num horário de 7 dias);
4. feriados não contam como a folga da semana;
5. a escolha segue a ordem dos dias: um dia já classificado não muda depois. Na semana em andamento, o último dia
   aparece previsto como folga até alguém folgar antes.

No resultado diário, o dia escolhido traz o aviso `WEEKLY_DAY_OFF` ("Folga da semana").

Exemplo (horário 08:00–16:00 todos os dias): semana 07–13/09 sem batida na quinta (10) e semana 14–20/09 sem batida
no domingo (20) ⇒ nenhuma falta, nenhuma hora extra, 12 dias × 8 h previstos.

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
* Dois registros do **mesmo** funcionário com menos de **2 minutos** (configurável em Administração → Configurações;
  0 desliga) de diferença ⇒ `DUPLICATE_RECORD`. Evita batida dupla por toque repetido. **Não** afeta funcionários
  diferentes: colegas que saem juntos batem um atrás do outro, sem espera.

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
| `late_minutes` | `max(0, ENTRY − entrada prevista)` — atraso (só em `WORKDAY`) |
| `early_leave_minutes` | `max(0, saída prevista − EXIT)` — saída antecipada (só em `WORKDAY`) |
| `missing_minutes` | `max(0, −saldo)` — horas faltantes no dia |
| `overtime_minutes` | `max(0, saldo)` — horas extras |
| `night_minutes` | Minutos trabalhados entre 22:00 e 05:00 (§7) |
| `balance_minutes` | `worked − planned`, após tolerância (§6) |
| `status` | `OK`, `ABSENT`, `INCOMPLETE`, `IN_PROGRESS`, `FUTURE`, `NONE` (folga/feriado sem batidas, fora do contrato) |
| `flags` | Lista: `INSUFFICIENT_BREAK`, `HOLIDAY_WORK`, `DAY_OFF_WORK` |
| `counts_for_bank` | Se o saldo entra no banco de horas |

### 5.1 Casos especiais

* **Falta:** dia `WORKDAY` passado sem nenhum registro ⇒ `ABSENT`, `worked=0`, `balance=−planned`, entra no banco.
* **Registro incompleto:** falta `EXIT`, ou `LUNCH_EXIT` sem `LUNCH_RETURN` ⇒ `INCOMPLETE`;
  `worked` soma só os pares fechados; saldo 0 e `counts_for_bank=false` até o administrador completar por ajuste.
* **Dia em andamento:** turno aberto dentro de `max_shift_hours`, ou o dia de hoje ainda sem batidas ⇒ `IN_PROGRESS`,
  fora do banco.
* **Dia futuro:** `FUTURE`, mostra a carga planejada, fora do banco.
* Minutos são contados em minutos inteiros (segundos são desprezados em cada período).
* **Folga trabalhada / fim de semana:** `planned=0`, todo minuto trabalhado é hora extra.
* **Feriado:** `planned=0`; trabalho no feriado é hora extra, com a flag `HOLIDAY_WORK`.
* **Intervalo insuficiente:** `worked > 6 h` e `break < 60 min`, ou `4 h < worked ≤ 6 h` e `break < 15 min`
  (CLT art. 71) ⇒ flag `INSUFFICIENT_BREAK`. O saldo continua sendo o tempo real trabalhado.

---

## 6. Tolerância (CLT art. 58 §1º)

* Variações de até **5 minutos por batida**, com limite de **10 minutos no dia**, não são computadas
  (configuráveis: `tolerance_per_mark_minutes`, `tolerance_daily_minutes`).
* Regra (somente dias `WORKDAY` completos):
  1. Calcula-se o desvio absoluto da **entrada** e da **saída** em relação ao horário fixo
     (o almoço é livre, então suas batidas não têm horário previsto).
  2. Se cada desvio ≤ 5 min, a soma ≤ 10 min **e** `|trabalhado − planejado| ≤ 10 min`
     ⇒ `balance=0`, `late=0`, `early_leave=0`, `overtime=0`, `missing=0`.
     (A última condição impede que um almoço longo seja "perdoado" só porque entrada e saída foram pontuais.)
  3. Caso contrário, os minutos são computados **integralmente** (não se desconta a tolerância).

---

## 7. Trabalho noturno

* Período noturno: **22:00 às 05:00** no fuso da empresa (configurável).
* O motor informa `night_minutes` (reais) e `night_minutes_reduced` (`× 60 / 52,5`, hora noturna reduzida — CLT art. 73).
* O saldo e o banco de horas usam **minutos reais**; os minutos noturnos são informativos para a folha.
* Turno noturno conta no dia da **entrada** prevista (ex.: turno 22:00–06:00 de quinta conta na quinta).
* Os períodos noturnos considerados são os que tocam o turno: 22:00 do dia anterior a 05:00, 22:00 a 05:00 do dia seguinte etc.

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

---

## 11. Horas para pagamento

Decisão do responsável (2026-10-01): **o sistema calcula somente as horas; o administrador multiplica pelo valor da hora.**
Nenhum valor em dinheiro é guardado ou calculado.

* Cada funcionário tem um **dia do pagamento** (1 a 31) no cadastro.
* **Ciclo de pagamento:** do dia seguinte ao pagamento anterior até o dia do pagamento, **inclusive**.
  Ex.: pagamento dia 5 → o pagamento de 05/09 cobre **06/08 a 05/09**.
* Se o dia não existir no mês (ex.: 31 em fevereiro), vale o **último dia do mês**.
* Para cada ciclo o sistema informa: horas trabalhadas, previstas, extras, faltantes, faltas e dias incompletos,
  em horas e minutos e em **horas decimais** (7h30 = 7,50), para multiplicar pelo valor da hora.
* **Horas a pagar = horas fixas (salário) + horas extras − horas faltantes** (decisão do responsável, 2026-10-01):
  * **horas fixas** = carga prevista do horário fixo em todos os dias de trabalho do ciclo (sem feriados, folgas
    e dias fora do contrato);
  * **horas extras** e **horas faltantes** = as mesmas do banco de horas (com a tolerância da CLT; faltas entram
    como faltantes; dias incompletos ou em andamento ainda não entram).
  * Ex.: 32 h fixas + 1,5 h extras − 8,5 h faltantes = **25 h a pagar**; o administrador multiplica pelo valor da hora.
  * Com o ciclo **em andamento**, as horas fixas já são as do ciclo inteiro (o salário), e as faltantes só contam
    os dias já passados; o valor só é definitivo quando o ciclo fecha.
* "Horas trabalhadas" (informativo) é a soma do tempo efetivamente batido, inclusive em folgas e feriados.
* Dias incompletos (batida faltando) são sinalizados: devem ser corrigidos antes de pagar.
* Ciclo ainda não encerrado aparece como "em andamento" (as horas ainda podem mudar).
* Dias antes da admissão não contam (`NOT_EMPLOYED`).

