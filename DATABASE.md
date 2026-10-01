# DATABASE.md

# Modelo de Dados — PostgreSQL 16

> **Status:** projetado na Fase 0. As tabelas serão criadas por migrations Alembic a partir da Fase 1
> (núcleo) e Fase 2 (registros, feriados, banco de horas). Biometria entra na Fase 5.
> Este documento deve ser atualizado a cada migration.

---

## 1. Convenções

* Nomes em inglês, `snake_case`, tabelas no plural.
* Chave primária `id BIGINT GENERATED ALWAYS AS IDENTITY`. IDs expostos na API são esses inteiros
  (a API exige autorização em todo acesso; não há dependência de IDs não-adivinháveis).
* Todo instante é `timestamptz`. Datas de calendário (dia de jornada, feriado) são `date`.
* Durações são `integer` em **minutos**.
* Tabelas mutáveis têm `created_at` e `updated_at`.
* Enums são `text` com `CHECK` (mais fácil de migrar que `CREATE TYPE`).
* Exclusão física apenas onde indicado; o padrão é desativar.
* Todas as alterações de schema via Alembic. Nunca alterar o banco manualmente.

---

## 2. Diagrama (resumo)

```
users ─┬─< user_roles >── roles ──< role_permissions >── permissions
       └─< refresh_tokens
employees ─┬─< employee_schedule_assignments >── work_schedules ──< work_schedule_days
           ├─< time_records >──── devices
           ├─< time_record_adjustments
           ├─< hour_bank_entries
           ├─< biometric_templates
           └─< biometric_consents
holidays          settings          audit_logs
```

`employees.user_id` (opcional) liga o funcionário a um login próprio (perfil FUNCIONARIO).

---

## 3. Tabelas — Fase 1

### users
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| email | text | único (case-insensitive: índice único em `lower(email)`) |
| name | text | not null |
| password_hash | text | argon2id |
| is_active | boolean | default true |
| failed_login_count | integer | default 0 |
| locked_until | timestamptz | null |
| last_login_at | timestamptz | null |
| created_at / updated_at | timestamptz | |

### roles / permissions / role_permissions / user_roles
* `roles(id, code UNIQUE, name)` — semeados: `ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`.
* `permissions(id, code UNIQUE, description)` — ex.: `employees:read`, `employees:write`, `records:adjust`.
* `role_permissions(role_id, permission_id)` PK composta.
* `user_roles(user_id, role_id)` PK composta.
* Papéis e permissões iniciais são criados por migration de dados (ver matriz em `SECURITY.md`).

### refresh_tokens
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| user_id | FK users | |
| token_hash | text | SHA-256 do token; único |
| family_id | uuid | para detectar reuso de token rotacionado |
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
| email | text | null |
| hire_date | date | not null |
| termination_date | date | null; `>= hire_date` |
| status | text | `ACTIVE` / `INACTIVE` |
| manager_user_id | FK users | null — escopo do perfil MANAGER |
| user_id | FK users | null, único — login próprio do funcionário |
| created_at / updated_at | timestamptz | |

Índices: `lower(name)` (pesquisa), `status`.

### work_schedules
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| name | text | único |
| type | text | `FIXED` / `FLEXIBLE` / `ROTATING` |
| cycle_length_days | integer | só `ROTATING` (ex.: 2 para 12x36) |
| cycle_reference_date | date | só `ROTATING`: data que corresponde à posição 0 |
| holidays_apply | boolean | default true |
| is_active | boolean | |
| created_at / updated_at | timestamptz | |

### work_schedule_days
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| schedule_id | FK work_schedules | |
| day_key | smallint | `FIXED`/`FLEXIBLE`: 0=segunda … 6=domingo; `ROTATING`: posição no ciclo |
| is_workday | boolean | |
| start_time | time | null em `FLEXIBLE` |
| end_time | time | `end_time < start_time` ⇒ termina no dia seguinte |
| break_start / break_end | time | opcionais (intervalo com horário fixo) |
| break_minutes | integer | duração do intervalo |
| planned_minutes | integer | carga do dia; validado contra horários quando houver |

Único: `(schedule_id, day_key)`.

### employee_schedule_assignments
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| schedule_id | FK work_schedules | |
| valid_from | date | not null |
| valid_to | date | null = vigente |

Sem sobreposição por funcionário: `EXCLUDE USING gist (employee_id WITH =, daterange(valid_from, valid_to, '[]') WITH &&)`
(requer extensão `btree_gist`).

### audit_logs
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| occurred_at | timestamptz | default now() |
| actor_type | text | `USER` / `DEVICE` / `SYSTEM` / `ANONYMOUS` |
| actor_user_id | FK users | null |
| actor_device_id | FK devices | null |
| action | text | ex.: `employee.update`, `auth.login_failed`, `record.rejected` |
| entity_type / entity_id | text / bigint | |
| before / after | jsonb | sem dados sensíveis (ver `SECURITY.md`) |
| ip / user_agent / request_id | text | |

Somente INSERT. O usuário de banco da aplicação não recebe `UPDATE`/`DELETE` nesta tabela (Fase 6).
Índices: `(entity_type, entity_id)`, `occurred_at`, `actor_user_id`.

### settings
Chave/valor (`key text PK`, `value jsonb`, `updated_at`) para parâmetros configuráveis de `BUSINESS-RULES.md`
(tolerâncias, `max_shift_hours`, período noturno, fuso etc.). Alterações auditadas.

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

(Criada na Fase 2 porque `time_records` a referencia.)

### time_records
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| type | text | `ENTRY` / `LUNCH_EXIT` / `LUNCH_RETURN` / `EXIT` |
| recorded_at | timestamptz | **horário oficial** (servidor); para `ADJUSTMENT`, o horário informado |
| workday_date | date | dia de jornada (ver `BUSINESS-RULES.md` §4.4) |
| source | text | `KIOSK` / `WEB` / `ADJUSTMENT` |
| identification_method | text | `FACE` / `MANUAL` |
| face_match_score | real | null |
| device_id | FK devices | null |
| created_by_user_id | FK users | null |
| ip | text | |
| voided_at | timestamptz | null — anulado por ajuste |
| voided_by_adjustment_id | FK time_record_adjustments | null |
| created_at | timestamptz | horário real de inserção |

Restrições:
* **Duplicidade:** índice único parcial `(employee_id, workday_date, type) WHERE voided_at IS NULL`.
* Índices: `(employee_id, recorded_at)`, `(workday_date)`.
* Sem `updated_at`: a única alteração permitida é preencher `voided_*` (feita pelo serviço de ajustes).

### time_record_adjustments
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| kind | text | `ADD` / `VOID` |
| record_id | FK time_records | registro criado (ADD) ou anulado (VOID) |
| reason | text | not null, mínimo 10 caracteres |
| created_by_user_id | FK users | not null; ≠ `employees.user_id` |
| created_at | timestamptz | |

### holidays
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| date | date | |
| name | text | |
| scope | text | `NATIONAL` / `STATE` / `MUNICIPAL` / `COMPANY` |
| recurring | boolean | repete todo ano no mesmo dia/mês |

Único: `(date)` para não recorrentes; recorrentes comparados por mês/dia.

### hour_bank_entries
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| entry_date | date | |
| minutes | integer | positivo (crédito) ou negativo (débito), ≠ 0 |
| kind | text | `OPENING_BALANCE` / `COMPENSATION` / `PAYOUT` / `CORRECTION` |
| reason | text | not null |
| created_by_user_id | FK users | |
| created_at | timestamptz | |

Imutável: correção de lançamento = novo lançamento compensatório.

### Resultados de cálculo
**Decisão:** na v1 os resultados diários **não são persistidos** — são calculados sob demanda a partir dos
registros (fonte de verdade). Evita inconsistência entre cache e registros após ajustes. Se a performance
exigir (Fase 6), adicionar tabela de cache `daily_summaries` invalidada por ajuste/feriado/jornada.

---

## 5. Tabelas — Fase 5 (biometria)

Detalhes de proteção em `BIOMETRICS.md`.

### biometric_consents
`id`, `employee_id`, `granted_at`, `revoked_at`, `term_version`, `recorded_by_user_id`.

### biometric_templates
| Coluna | Tipo | Regras |
|---|---|---|
| id | bigint PK | |
| employee_id | FK employees | |
| model_version | text | ex.: `sface-2021dec` — templates de modelos diferentes não são comparáveis |
| ciphertext | bytea | embedding cifrado (AES-256-GCM) |
| nonce | bytea | 12 bytes |
| key_id | text | identifica a chave usada (rotação) |
| quality_score | real | |
| created_at | timestamptz | |
| deleted_at | timestamptz | exclusão lógica imediata + expurgo físico (ver `BIOMETRICS.md`) |

**Nunca** existe coluna de imagem facial.
