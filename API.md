# API.md

# API REST — v1

> **Status:** projetado na Fase 0. Os endpoints serão implementados nas Fases 1–3 e 5 (coluna "Fase").
> A documentação OpenAPI gerada pelo FastAPI (`/api/v1/openapi.json`, UI em `/api/docs`) passa a ser a
> referência detalhada a partir da Fase 3; este arquivo mantém a visão geral e as convenções.

---

## 1. Convenções

* Base: `/api/v1`. JSON em UTF-8. Nomes de campos em `snake_case`.
* Instantes em ISO 8601 com fuso (`2026-09-01T08:02:13-03:00`). Datas como `YYYY-MM-DD` (fuso da empresa).
* Durações em **minutos** (inteiros).
* Autenticação: `Authorization: Bearer <access_token>` (usuários) ou `Authorization: Device <token>` (kiosk).

### Paginação
`?page=1&page_size=50` (máx. 200). Resposta:
```json
{ "items": [...], "page": 1, "page_size": 50, "total": 132 }
```

### Ordenação
`?sort=name` ou `?sort=-recorded_at` (prefixo `-` = decrescente). Cada recurso documenta os campos aceitos.

### Filtros
Parâmetros de query específicos por recurso (ex.: `?status=ACTIVE&q=maria`).
Períodos: `date_from` e `date_to`, **inclusivos** (ver `BUSINESS-RULES.md` §10).

### Erros
Formato único para todos os erros:
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

| HTTP | Uso | Códigos |
|---|---|---|
| 400 | Requisição malformada | `BAD_REQUEST` |
| 401 | Não autenticado / token inválido ou expirado | `UNAUTHENTICATED`, `TOKEN_EXPIRED` |
| 403 | Sem permissão | `FORBIDDEN`, `DEVICE_NOT_AUTHORIZED` |
| 404 | Recurso inexistente ou fora do escopo do usuário | `NOT_FOUND`, `EMPLOYEE_NOT_FOUND` |
| 409 | Conflito de regra de negócio | `DUPLICATE_RECORD`, `INVALID_SEQUENCE`, `EMPLOYEE_INACTIVE`, `NO_APPLICABLE_SCHEDULE`, `SCHEDULE_OVERLAP`, `CONFLICT` |
| 422 | Validação de campos | `VALIDATION_ERROR` (com lista de campos em `details`) |
| 423 | Conta bloqueada | `ACCOUNT_LOCKED` |
| 429 | Limite de taxa | `RATE_LIMITED` |
| 500 | Erro interno (sem detalhes) | `INTERNAL_ERROR` |

Recursos fora do escopo do usuário retornam **404** (não revela existência).

---

## 2. Endpoints

### Saúde
| Método | Rota | Auth | Fase |
|---|---|---|---|
| GET | `/health/live` | — | 1 |
| GET | `/health/ready` (verifica banco) | — | 1 |

### Autenticação
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` → `{access_token, expires_in, user}` + cookie de refresh | 1 |
| POST | `/auth/refresh` | Cookie de refresh → novo access token (rotaciona refresh) | 1 |
| POST | `/auth/logout` | Revoga refresh atual | 1 |
| GET | `/auth/me` | Usuário atual, papéis e permissões efetivas | 1 |

### Usuários e permissões (ADMIN)
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/users` | 1 |
| GET / PATCH | `/users/{id}` | 1 |
| POST | `/users/{id}/activate`, `/users/{id}/deactivate` | 1 |
| PUT | `/users/{id}/roles` | 1 |
| GET | `/roles` (com permissões) | 1 |
| GET | `/permissions` | 1 |

### Funcionários
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/employees` | Filtros: `q` (nome/matrícula), `status`, `manager_user_id`. Ordenação: `name`, `registration_number`, `hire_date` | 1 |
| POST | `/employees` | Cadastro | 1 |
| GET / PATCH | `/employees/{id}` | Detalhe / edição | 1 |
| POST | `/employees/{id}/activate`, `/employees/{id}/deactivate` | | 1 |
| GET | `/employees/{id}/history` | Alterações cadastrais (da auditoria) | 1 |
| GET / POST | `/employees/{id}/schedule-assignments` | Vigências de jornada | 1 |

### Jornadas
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/schedules` | 1 |
| GET / PUT | `/schedules/{id}` (com os dias) | 1 |
| POST | `/schedules/{id}/activate`, `/schedules/{id}/deactivate` | 1 |

### Feriados
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/holidays` (filtro por ano/período) | 2 |
| PATCH / DELETE | `/holidays/{id}` | 2 |

### Registros de ponto e histórico
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/time-records` | Histórico. Filtros: `employee_id`, `date_from`, `date_to`, `type`, `source`, `device_id`, `include_voided`. Ordenação: `recorded_at` | 2 |
| GET | `/time-records/{id}` | Detalhe, com ajustes relacionados | 2 |
| POST | `/time-records` | Registro web por usuário autorizado (`records:create_web`). Corpo: `{employee_id, type}` — **sem horário** | 2 |
| GET | `/employees/{id}/time-records/status` | Estado do dia de jornada atual e próximos tipos permitidos | 2 |
| POST | `/time-records/adjustments` | Ajuste: `{kind: ADD, employee_id, type, recorded_at, reason}` ou `{kind: VOID, record_id, reason}` | 2 |
| GET | `/time-records/adjustments` | Lista de ajustes (filtros por funcionário/período) | 3 |

### Cálculo e banco de horas
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/employees/{id}/workdays?date_from&date_to` | Resultado diário do motor (ver `BUSINESS-RULES.md` §5) | 2 |
| GET | `/employees/{id}/hour-bank?date_from&date_to` | Saldo anterior, dias, totais, saldo final | 2 |
| GET / POST | `/employees/{id}/hour-bank/entries` | Lançamentos manuais | 2 |
| GET | `/hour-bank/summary?date_from&date_to` | Saldo por funcionário (paginado, respeita escopo) | 3 |

### Auditoria
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/audit-logs` | Filtros: `entity_type`, `entity_id`, `actor_user_id`, `action`, `date_from`, `date_to` | 3 |

### Dispositivos (ADMIN)
| Método | Rota | Fase |
|---|---|---|
| GET / POST | `/devices` (POST devolve o token **uma vez**) | 2 |
| POST | `/devices/{id}/deactivate`, `/devices/{id}/rotate-token` | 2 |

### Configurações (ADMIN)
| Método | Rota | Fase |
|---|---|---|
| GET / PATCH | `/settings` | 2 |

### Kiosk (token de dispositivo)
| Método | Rota | Descrição | Fase |
|---|---|---|---|
| GET | `/kiosk/ping` | Valida token, atualiza `last_seen_at`, retorna horário do servidor (exibição) | 2 |
| POST | `/kiosk/identify` | `multipart` com 1 frame JPEG → `{identification_token, employee: {id, name}, allowed_types, expires_in}` | 5 |
| POST | `/kiosk/records` | `{identification_token, type}` → registro criado com horário oficial | 5 |

### Biometria (HR/ADMIN)
| Método | Rota | Fase |
|---|---|---|
| POST / DELETE | `/employees/{id}/biometric-consent` | 5 |
| POST | `/employees/{id}/biometric-templates` (frames de cadastro) | 5 |
| DELETE | `/employees/{id}/biometric-templates` | 5 |
| GET | `/employees/{id}/biometric-status` (tem consentimento? quantos templates? nunca os dados) | 5 |

---

## 3. Exemplo — registro de ponto bem-sucedido

`POST /api/v1/time-records` → `201`
```json
{
  "id": 1042,
  "employee_id": 7,
  "type": "ENTRY",
  "recorded_at": "2026-09-01T08:02:13-03:00",
  "workday_date": "2026-09-01",
  "source": "WEB",
  "identification_method": "MANUAL",
  "device_id": null
}
```
