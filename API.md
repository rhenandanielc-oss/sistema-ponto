# API.md

# API REST — v1

> **Status:** todos os endpoints abaixo estão **implementados** (Fases 1–5). O OpenAPI gerado pelo FastAPI
> (`/api/v1/openapi.json`, UI em `/api/docs`) é a referência detalhada dos campos. Em produção ambos ficam
> desligados; use o ambiente de desenvolvimento ou `python -m app.cli export-openapi`.

---

## 1. Convenções

* Base: `/api/v1`. JSON UTF-8. Campos em `snake_case`.
* Instantes ISO 8601 com fuso. Respostas sempre no fuso da empresa (`2026-09-01T08:02:13-03:00`);
  em entradas, horário sem fuso é interpretado no fuso da empresa. Datas `YYYY-MM-DD` (fuso da empresa).
* Durações em **minutos**.
* Autenticação:
  * administrador: `Authorization: Bearer <access_token>`;
  * kiosk: `Authorization: Device <token>`; após o reconhecimento facial, o kiosk envia também o
    `identification_token` no corpo.

### Paginação
`?page=1&page_size=50` (máx. 200) → `{ "items": [...], "page": 1, "page_size": 50, "total": 132 }`

### Ordenação
`?sort=name` ou `?sort=-recorded_at`.

### Filtros
Parâmetros por recurso. Períodos: `date_from`, `date_to`, **inclusivos**.

### Erros
```json
{
  "error": {
    "code": "INVALID_SEQUENCE",
    "message": "Registro fora de sequência. Próximo registro esperado: LUNCH_RETURN.",
    "details": { "expected": ["LUNCH_RETURN"] },
    "request_id": "8f1c..."
  }
}
```

| HTTP | Códigos |
|---|---|
| 400 | `BAD_REQUEST` |
| 413 | `PAYLOAD_TOO_LARGE` (corpo acima de 1 MB) |
| 401 | `UNAUTHENTICATED`, `TOKEN_EXPIRED`, `IDENTIFICATION_REQUIRED` |
| 403 | `FORBIDDEN`, `DEVICE_NOT_AUTHORIZED` |
| 404 | `NOT_FOUND`, `EMPLOYEE_NOT_FOUND` |
| 409 | `DUPLICATE_RECORD`, `INVALID_SEQUENCE`, `EMPLOYEE_INACTIVE`, `NO_APPLICABLE_SCHEDULE`, `SCHEDULE_OVERLAP`, `CONSENT_REQUIRED`, `CONFLICT` |
| 422 | `VALIDATION_ERROR`, `FACE_NOT_FOUND`, `MULTIPLE_FACES`, `LOW_QUALITY`, `INVALID_IMAGE` |
| 423 | `ACCOUNT_LOCKED` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |

`FACE_NOT_RECOGNIZED` (404) é devolvido por `/kiosk/identify` quando ninguém corresponde.

---

### Limites de requisição

| Rota | Limite por IP | Resposta ao exceder |
|---|---|---|
| `POST /auth/login` | 20 por minuto | 429 `RATE_LIMITED` + cabeçalho `Retry-After` |
| `POST /auth/refresh` | 60 por minuto | idem |
| `/kiosk/*` | 120 por minuto (tokens inválidos também contam) | idem |

Toda resposta traz `X-Request-ID`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer` e `Cache-Control: no-store`.

---

## 2. Endpoints — administrador

Todos exigem administrador autenticado, exceto `/health/*` e `/auth/login|refresh|logout` (estes dois últimos usam o cookie de refresh).

### Saúde
| Método | Rota | Fase |
|---|---|---|
| GET | `/health/live` | 1 |
| GET | `/health/ready` (verifica banco) | 1 |

### Autenticação
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` → `{access_token, expires_in, admin}` + cookie de refresh | 1 |
| POST | `/auth/refresh` | Novo access token (rotaciona refresh) | 1 |
| POST | `/auth/logout` | Revoga refresh | 1 |
| GET | `/auth/me` | Administrador atual | 1 |

### Administradores
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/admins` | 1 |
| PATCH | `/admins/{id}` (nome, senha) | 1 |
| POST | `/admins/{id}/activate`, `/admins/{id}/deactivate` (não pode desativar a si mesmo nem o último ativo) | 1 |

### Funcionários e horário fixo
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/employees` | Filtros: `q` (nome/matrícula), `status`. Ordenação: `name`, `registration_number`, `hire_date` | 1 |
| POST | `/employees` | Cadastro **com horário fixo inicial**: `{name, registration_number, cpf?, hire_date, schedule}`. `schedule` na forma simples `{weekdays?: ["segunda", …, "sexta"], start_time: "08:00", end_time: "16:00", lunch_minutes?: 60}` (dias por nome ou número; padrão segunda a sexta) ou dia a dia `{days: [{weekday, start_time, end_time, lunch_minutes?}]}`; em ambas, `weekly_day_off: true` ativa a folga semanal em qualquer dia (`BUSINESS-RULES.md` §3.2) (o rosto é cadastrado na mesma tela — endpoint de biometria, Fase 5) | 1 |
| GET / PATCH | `/employees/{id}` | Detalhe (inclui horário vigente e carga diária calculada) / edição cadastral | 1 |
| POST | `/employees/{id}/activate`, `/employees/{id}/deactivate` | | 1 |
| GET | `/employees/{id}/history` | Alterações cadastrais (auditoria) | 1 |
| GET | `/employees/{id}/schedules` | Vigências do horário fixo | 1 |
| POST | `/employees/{id}/schedules` | Novo horário a partir de `valid_from` (encerra o anterior em `valid_from − 1`) | 1 |

### Pagamento (horas do ciclo)
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/employees/{id}/payroll?payment_month=AAAA-MM` ou `?reference_date=AAAA-MM-DD` | Horas do ciclo de pagamento (padrão: ciclo que contém hoje), em minutos e em horas decimais: fixas (`planned_*`), extras, faltantes e **a pagar** (`payable_*` = fixas + extras − faltantes) | 4 |
| GET | `/payroll?payment_month&reference_date&q&status` | Mesmo cálculo para todos os funcionários, cada um no seu ciclo (paginado) | 4 |

O cadastro (`POST /employees`) exige `payday` (1 a 31); `PATCH /employees/{id}` permite alterá-lo.

### Consumo do funcionário (valores em centavos)
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET / POST | `/consumption-items` | Itens com preço (`?include_inactive=false` só ativos) | 6 |
| PATCH | `/consumption-items/{id}` | Nome, preço, ativo | 6 |
| GET | `/employees/{id}/consumption?date_from&date_to` | Lançamentos e `total_cents` (padrão: ciclo de pagamento atual) | 6 |
| POST | `/employees/{id}/consumption` | `{item_id, quantity?, entry_date?}` ou `{description, unit_price_cents, quantity?, entry_date?}` | 6 |
| POST | `/consumption/{entry_id}/cancel` | `{reason}` | 6 |

`/payroll` e `/employees/{id}/payroll` trazem `consumption_cents` (consumo do ciclo, a descontar); `/kiosk/hour-bank`
traz `pay_period_consumption_cents`.

### Feriados
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/holidays` | 2 |
| PATCH / DELETE | `/holidays/{id}` | 2 |

### Registros, histórico e ajustes
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/time-records` | Histórico. Filtros: `employee_id`, `date_from`, `date_to`, `type`, `source`, `device_id`, `include_voided`. Ordenação: `recorded_at` | 2 |
| GET | `/time-records/{id}` | Detalhe com ajustes | 2 |
| POST | `/time-records/adjustments` | `{kind: ADD, employee_id, type, recorded_at, reason}` ou `{kind: VOID, record_id, reason}` | 2 |
| GET | `/time-records/adjustments` | Lista de ajustes (filtro `employee_id`) | 2 |

### Cálculo e banco de horas
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/employees/{id}/workdays?date_from&date_to` | Resultado diário (`BUSINESS-RULES.md` §5) | 2 |
| GET | `/employees/{id}/hour-bank?date_from&date_to` | Saldo anterior, dias, totais, saldo final | 2 |
| GET / POST | `/employees/{id}/hour-bank/entries` | Lançamentos manuais | 2 |
| GET | `/hour-bank/summary?date_from&date_to&q&status` | Saldo de todos os funcionários no período, ordenado por nome (paginado) | 3 |

### Auditoria, dispositivos e configurações
| Método | Rota | Fase |
|---|---|---|
| GET | `/audit-logs` (filtros: `entity_type`, `entity_id`, `action` exata ou prefixo terminado em `.` — ex.: `employee.` —, `actor_admin_id`, `date_from`, `date_to`; ordenação `occurred_at`) | 3 |
| GET / POST | `/devices` (POST devolve o token **uma vez**) | 2 |
| POST | `/devices/{id}/activate`, `/devices/{id}/deactivate`, `/devices/{id}/rotate-token` | 2 |
| GET / PATCH | `/settings` (tolerâncias, intervalo mínimo entre batidas, turno máximo, janela de entrada antecipada, período noturno, tempo da tela do kiosk) | 2 |

### Biometria
| Método | Rota | Fase |
|---|---|---|
| POST / DELETE | `/employees/{id}/biometric-consent` (DELETE revoga e exclui as fotos) | 5 |
| POST | `/employees/{id}/biometric-templates` (`multipart`, campo `image`: **uma** foto JPEG/PNG por chamada, até 5 por funcionário; exige consentimento) | 5 |
| DELETE | `/employees/{id}/biometric-templates` | 5 |
| GET | `/employees/{id}/biometric-status` (consentimento e quantidade de templates; nunca os dados) | 5 |

---

## 3. Endpoints — kiosk (token de dispositivo)

| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/kiosk/ping` | Valida o dispositivo; retorna horário do servidor para exibição | 2 |
| POST | `/kiosk/identify` | `multipart` (campo `image`, 1 quadro JPEG/PNG) → `{identification_token, expires_in, employee_name, workday_date, allowed_types, hour_bank_screen_seconds}` | 5 |
| POST | `/kiosk/records` | `{identification_token, type}` → batida criada com horário oficial; consome o token | 5 |
| POST | `/kiosk/hour-bank` | `{identification_token}` → saldo acumulado, extras/faltantes/faltas do mês, extras/faltantes do ciclo de pagamento e dias do mês — **só do funcionário identificado**; não consome o token | 5 |

Nenhum endpoint do kiosk recebe id de funcionário.

---

## 4. Exemplo — batida no kiosk

`POST /api/v1/kiosk/records` `{"identification_token": "…", "type": "ENTRY"}` → `201`
```json
{
  "id": 1042,
  "employee": { "name": "Maria Souza" },
  "type": "ENTRY",
  "recorded_at": "2026-09-01T08:02:13-03:00",
  "workday_date": "2026-09-01"
}
```
