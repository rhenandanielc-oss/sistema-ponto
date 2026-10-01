# DATABASE.md

# Modelo de Dados — PostgreSQL 16

> **Status:** projetado na Fase 0 (revisado em 2026-10-01). As tabelas serão criadas por migrations Alembic a partir
> da Fase 1 (núcleo) e Fase 2 (registros, feriados, banco de horas). Biometria entra na Fase 5.
> Este documento deve ser atualizado a cada migration.

---

## 1. Convenções

* Nomes em inglês, `snake_case`, tabelas no plural.
* Chave primária `id BIGINT GENERATED ALWAYS AS IDENTITY`.
* Todo instante é `timestamptz`. Datas de calendário (dia de jornada, feriado, vigência) são `date`.
* Durações são `integer` em **minutos**.
* Tabelas mutáveis têm `created_at` e `updated_at`.
* Enums são `text` com `CHECK`.
* Exclusão física apenas onde indicado; o padrão é desativar.
* Todas as alterações de schema via Alembic.

---

## 2. Diagrama (resumo)

```
admins ──< refresh_tokens
employees ─┬─< employee_schedules ──< employee_schedule_days
           ├─< time_records >──── devices
           ├─< time_record_adjustments
           ├─< hour_bank_entries
           ├─< biometric_templates
           └─< biometric_consents
holidays          settings          audit_logs
```

Funcionários **não** têm login: não existe vínculo entre `employees` e `admins`.

---

## 3. Tabelas — Fase 1

### admins
Únicos usuários com senha.

| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| email | text | único (índice em `lower(email)`) |
| name | text | not null |
| password_hash | text | argon2id |
| is_active | boolean | default true |
| failed_login_count | integer | default 0 |
| locked_until | timestamptz | null |
| last_login_at | timestamptz | null |
| created_at / updated_at | timestamptz | |

O primeiro administrador é criado por comando de linha (`python -m app.cli create-admin`), nunca por migration
com senha fixa.

### refresh_tokens
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| admin_id | FK admins | |
| token_hash | text | SHA-256; único |
| family_id | uuid | detecção de reuso de token rotacionado |
| expires_at | timestamptz | |
| revoked_at | timestamptz | null |
| created_at | timestamptz | |
| user_agent / ip | text | |

### employees
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| registration_number | text | **único** (matrícula) |
| name | text | not null |
| cpf | text | único quando não nulo; 11 dígitos validados |
| hire_date | date | not null |
| termination_date | date | null; `>= hire_date` |
| status | text | `ACTIVE` / `INACTIVE` |
| created_at / updated_at | timestamptz | |

Índices: `lower(name)` (pesquisa), `status`.

### employee_schedules
Vigência do horário fixo do funcionário.

| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| valid_from | date | not null |
| valid_to | date | null = vigente; `>= valid_from` |
| created_by_admin_id | FK admins | null (criado por comando de linha) |
| created_at | timestamptz | |

Sem sobreposição por funcionário:
`EXCLUDE USING gist (employee_id WITH =, daterange(valid_from, valid_to, '[]') WITH &&)` (extensão `btree_gist`).

### employee_schedule_days
| Coluna | Tipo | Regras |
|---|---|---|
| schedule_id | FK employee_schedules (on delete cascade) | |
| weekday | smallint | 0=segunda … 6=domingo |
| start_time | time | entrada prevista |
| lunch_start | time | null = dia sem intervalo |
| lunch_end | time | null se `lunch_start` nulo |
| end_time | time | saída prevista; `end_time <= start_time` ⇒ termina no dia seguinte |

PK `(schedule_id, weekday)`. Dia ausente = folga. Toda vigência tem ao menos um dia.
A carga planejada é **calculada** a partir dos horários (não é armazenada). O serviço valida: intervalo dentro do
turno, `lunch_start < lunch_end`, turno com até 16 h.

### audit_logs
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| occurred_at | timestamptz | default now() |
| actor_type | text | `ADMIN` / `DEVICE` / `EMPLOYEE_FACE` / `SYSTEM` / `ANONYMOUS` |
| actor_admin_id | FK admins | null |
| actor_device_id | FK devices | null |
| actor_employee_id | FK employees | null (funcionário identificado pelo rosto) |
| action | text | ex.: `employee.update`, `auth.login_failed`, `record.rejected`, `kiosk.hour_bank_viewed` |
| entity_type / entity_id | text / bigint | |
| before / after | jsonb | sem dados sensíveis (ver `SECURITY.md`) |
| ip / user_agent / request_id | text | |

Somente INSERT (o usuário de banco da aplicação não recebe `UPDATE`/`DELETE` nesta tabela — Fase 6).
Índices: `(entity_type, entity_id)`, `occurred_at`.

### settings
`key text PK`, `value jsonb`, `updated_at`. Parâmetros configuráveis de `BUSINESS-RULES.md`
(tolerâncias, `max_shift_hours`, intervalo mínimo entre batidas, período noturno, tempo da tela do kiosk, fuso).
Alterações auditadas.

---

## 4. Tabelas — Fase 2

### devices
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| name | text | ex.: "Recepção" |
| token_hash | text | único; token exibido uma vez |
| is_active | boolean | |
| last_seen_at | timestamptz | |
| created_at / updated_at | timestamptz | |

### time_records
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| type | text | `ENTRY` / `LUNCH_EXIT` / `LUNCH_RETURN` / `EXIT` |
| recorded_at | timestamptz | **horário oficial** (servidor); em `ADJUSTMENT`, o horário informado |
| workday_date | date | dia de jornada (`BUSINESS-RULES.md` §4.4) |
| source | text | `KIOSK` / `ADJUSTMENT` |
| face_match_score | real | null em ajustes |
| device_id | FK devices | null em ajustes |
| ip | text | |
| voided_at | timestamptz | null — anulado por ajuste |
| voided_by_adjustment_id | FK time_record_adjustments | null |
| created_at | timestamptz | horário real de inserção |

Restrições:
* **Duplicidade:** índice único parcial `(employee_id, workday_date, type) WHERE voided_at IS NULL`.
* Índices: `(employee_id, recorded_at)`, `(workday_date)`.
* A única alteração permitida é preencher `voided_*` (serviço de ajustes).

### time_record_adjustments
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| kind | text | `ADD` / `VOID` |
| record_id | FK time_records | registro criado (ADD) ou anulado (VOID) |
| reason | text | not null, mínimo 10 caracteres |
| created_by_admin_id | FK admins | not null |
| created_at | timestamptz | |

### holidays
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| date | date | |
| name | text | |
| recurring | boolean | repete todo ano no mesmo dia/mês |

### hour_bank_entries
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| entry_date | date | |
| minutes | integer | ≠ 0 (positivo = crédito, negativo = débito) |
| kind | text | `OPENING_BALANCE` / `COMPENSATION` / `PAYOUT` / `CORRECTION` |
| reason | text | not null |
| created_by_admin_id | FK admins | |
| created_at | timestamptz | |

Imutável: correção = novo lançamento compensatório.

### Resultados de cálculo
**Decisão:** na v1 os resultados diários **não são persistidos** — são calculados sob demanda a partir dos registros.
Se a performance exigir (Fase 6), adicionar cache `daily_summaries` invalidado por ajuste/feriado/horário.

---

## 5. Tabelas — Fase 5 (biometria)

Detalhes em `BIOMETRICS.md`.

### biometric_consents
`id`, `employee_id`, `granted_at`, `revoked_at`, `term_version`, `recorded_by_admin_id`.

### biometric_templates
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| model_version | text | templates de modelos diferentes não são comparáveis |
| ciphertext | bytea | embedding cifrado (AES-256-GCM) |
| nonce | bytea | 12 bytes |
| key_id | text | rotação de chave |
| quality_score | real | |
| created_at | timestamptz | |
| deleted_at | timestamptz | exclusão lógica imediata + expurgo físico |

**Nunca** existe coluna de imagem facial.
