# API.md

# API REST — v1

> **Status:** endpoints das Fases 1 e 2 **implementados** (todos os marcados com 1 ou 2 abaixo).
> Os demais serão implementados nas Fases 3 e 5. O OpenAPI gerado pelo FastAPI
> (`/api/v1/openapi.json`, UI em `/api/docs`) é a referência detalhada dos campos.

---

## 1. Convenções

* Base: `/api/v1`. JSON UTF-8. Campos em `snake_case`.
* Instantes ISO 8601 com fuso. Respostas sempre no fuso da empresa (`2026-09-01T08:02:13-03:00`);
  entradas precisam informar o fuso (horário sem fuso é recusado). Datas `YYYY-MM-DD` (fuso da empresa).
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
| 401 | `UNAUTHENTICATED`, `TOKEN_EXPIRED`, `IDENTIFICATION_REQUIRED` |
| 403 | `FORBIDDEN`, `DEVICE_NOT_AUTHORIZED` |
| 404 | `NOT_FOUND`, `EMPLOYEE_NOT_FOUND` |
| 409 | `DUPLICATE_RECORD`, `INVALID_SEQUENCE`, `EMPLOYEE_INACTIVE`, `NO_APPLICABLE_SCHEDULE`, `SCHEDULE_OVERLAP`, `CONFLICT` |
| 422 | `VALIDATION_ERROR`, `FACE_NOT_FOUND`, `MULTIPLE_FACES`, `LOW_QUALITY` |
| 423 | `ACCOUNT_LOCKED` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |

`FACE_NOT_RECOGNIZED` (404) é devolvido por `/kiosk/identify` quando ninguém corresponde.

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
| POST | `/employees` | Cadastro **com horário fixo inicial**: `{name, registration_number, cpf?, hire_date, schedule}`. `schedule` na forma simples `{weekdays?: ["segunda", …, "sexta"], start_time: "08:00", end_time: "16:00", lunch_minutes?: 60}` (dias por nome ou número; padrão segunda a sexta) ou dia a dia `{days: [{weekday, start_time, end_time, lunch_minutes?}]}` (o rosto é cadastrado na mesma tela — endpoint de biometria, Fase 5) | 1 |
| GET / PATCH | `/employees/{id}` | Detalhe (inclui horário vigente e carga diária calculada) / edição cadastral | 1 |
| POST | `/employees/{id}/activate`, `/employees/{id}/deactivate` | | 1 |
| GET | `/employees/{id}/history` | Alterações cadastrais (auditoria) | 1 |
| GET | `/employees/{id}/schedules` | Vigências do horário fixo | 1 |
| POST | `/employees/{id}/schedules` | Novo horário a partir de `valid_from` (encerra o anterior em `valid_from − 1`) | 1 |

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
| GET | `/hour-bank/summary?date_from&date_to` | Saldo de todos os funcionários (paginado) | 3 |

### Auditoria, dispositivos e configurações
| Método | Rota | Fase |
|---|---|---|
| GET | `/audit-logs` (filtros: `entity_type`, `entity_id`, `action`, `date_from`, `date_to`) | 3 |
| GET / POST | `/devices` (POST devolve o token **uma vez**) | 2 |
| POST | `/devices/{id}/activate`, `/devices/{id}/deactivate`, `/devices/{id}/rotate-token` | 2 |
| GET / PATCH | `/settings` (tolerâncias, intervalo mínimo entre batidas, turno máximo, janela de entrada antecipada, período noturno, tempo da tela do kiosk) | 2 |

### Biometria
| Método | Rota | Fase |
|---|---|---|
| POST / DELETE | `/employees/{id}/biometric-consent` | 5 |
| POST | `/employees/{id}/biometric-templates` (frames de cadastro) | 5 |
| DELETE | `/employees/{id}/biometric-templates` | 5 |
| GET | `/employees/{id}/biometric-status` (consentimento e quantidade de templates; nunca os dados) | 5 |

---

## 3. Endpoints — kiosk (token de dispositivo)

| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/kiosk/ping` | Valida o dispositivo; retorna horário do servidor para exibição | 2 |
| POST | `/kiosk/identify` | `multipart` com 1 frame JPEG → `{identification_token, expires_in, employee: {name}, allowed_types}` | 5 |
| POST | `/kiosk/records` | `{identification_token, type}` → batida criada com horário oficial; consome o token | 5 |
| POST | `/kiosk/hour-bank` | `{identification_token, date_from?, date_to?}` (padrão: mês atual) → banco de horas **do funcionário identificado** | 5 |

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
