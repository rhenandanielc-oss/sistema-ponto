# SECURITY.md

# Segurança

> **Status:** projetado na Fase 0. Implementação: autenticação/autorização na Fase 1, kiosk na Fase 2/5,
> endurecimento e revisão final na Fase 6.

---

## 1. Ameaças consideradas

| Ameaça | Mitigação principal |
|---|---|
| Funcionário registra ponto por outro ("ponto amigo") | Reconhecimento facial no kiosk; auditoria com score e dispositivo; limitações em `BIOMETRICS.md` |
| Manipulação do horário pelo cliente | Horário oficial definido pelo servidor |
| Alteração retroativa de registros | Registros imutáveis; ajustes com justificativa, autor e auditoria |
| Acesso indevido a dados de outros funcionários | RBAC + escopo por gestor; checagem em todo endpoint |
| Roubo de sessão | Access token curto, refresh em cookie `HttpOnly`, rotação com detecção de reuso |
| Força bruta de senha | Bloqueio progressivo + limitação de taxa |
| Kiosk roubado / token vazado | Token de dispositivo revogável; escopo limitado; auditoria de `last_seen_at` e IP |
| Vazamento de dados biométricos | Sem imagens armazenadas; templates cifrados; chave fora do banco |
| Segredos no Git | `.env` ignorado; `.env.example` sem valores; revisão antes de commit |

---

## 2. Autenticação de usuários

* Login: `POST /api/v1/auth/login` com e-mail e senha.
* Senhas com **argon2id** (parâmetros padrão do `argon2-cffi`). Mínimo de 10 caracteres.
* **Access token:** JWT HS256, validade **15 min**, claims `sub`, `roles`, `exp`, `iat`, `jti`.
  Enviado no header `Authorization: Bearer`. Mantido **apenas em memória** no frontend (nunca em `localStorage`).
* **Refresh token:** valor aleatório de 256 bits, em cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`,
  validade **8 horas** (configurável). Armazenado como hash SHA-256. **Rotação** a cada uso; se um token já
  rotacionado for reutilizado, toda a família é revogada (indício de roubo).
* Logout revoga o refresh token atual.
* Usuário desativado: refresh tokens revogados imediatamente; access tokens expiram em até 15 min.
* **Bloqueio:** 5 falhas consecutivas ⇒ bloqueio de 15 min. Mensagem de erro genérica ("credenciais inválidas")
  para não revelar se o e-mail existe.
* Login, falha de login, logout e bloqueio são auditados.

### CSRF
O refresh token é o único dado enviado por cookie, com `SameSite=Strict` e restrito ao caminho `/auth`.
As demais rotas usam `Authorization`, que não é enviado automaticamente pelo navegador.

---

## 3. Autenticação de dispositivos (kiosk)

* Administrador cadastra o dispositivo e recebe um token aleatório (256 bits) **exibido uma única vez**.
* O kiosk envia `Authorization: Device <token>`. O banco guarda só o hash.
* O token de dispositivo **só** acessa endpoints `/api/v1/kiosk/*`.
* Desativar o dispositivo invalida o token imediatamente.
* No terminal, o token fica armazenado no navegador do kiosk (procedimento de instalação na Fase 5/6).

---

## 4. Autorização (RBAC)

Perfis iniciais e permissões:

| Permissão | ADMIN | HR | MANAGER | EMPLOYEE |
|---|:-:|:-:|:-:|:-:|
| `users:read` / `users:write` | ✔ | | | |
| `roles:write` | ✔ | | | |
| `devices:write` | ✔ | | | |
| `settings:write` | ✔ | | | |
| `audit:read` | ✔ | ✔ | | |
| `employees:read` | ✔ | ✔ | escopo | próprio |
| `employees:write` | ✔ | ✔ | | |
| `schedules:read` | ✔ | ✔ | ✔ | |
| `schedules:write` | ✔ | ✔ | | |
| `holidays:write` | ✔ | ✔ | | |
| `records:read` | ✔ | ✔ | escopo | próprio |
| `records:create_web` | ✔ | ✔ | | |
| `records:adjust` | ✔ | ✔ | escopo | |
| `hour_bank:read` | ✔ | ✔ | escopo | próprio |
| `hour_bank:adjust` | ✔ | ✔ | | |
| `biometrics:enroll` | ✔ | ✔ | | |

* **escopo:** apenas funcionários com `manager_user_id` = usuário logado.
* **próprio:** apenas o funcionário vinculado ao usuário (`employees.user_id`).
* Ninguém ajusta os próprios registros nem o próprio banco de horas.
* A checagem acontece no backend em **todo** endpoint (dependência FastAPI), nunca só no frontend.
* Acesso negado retorna 403 e é auditado para endpoints administrativos.

---

## 5. Proteção da API

* HTTPS obrigatório em produção (HSTS no proxy).
* CORS restrito à origem do frontend.
* Limitação de taxa (por IP e por usuário/dispositivo) em login e endpoints do kiosk.
* Tamanho máximo de corpo: 1 MB (frames do kiosk são JPEG pequenos).
* Erros nunca expõem stack trace nem SQL (formato padrão em `API.md`).
* Cabeçalhos de segurança: `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy` no frontend.
* Consultas apenas via ORM/parâmetros (sem SQL concatenado).

---

## 6. Segredos

* Configuração via variáveis de ambiente (`pydantic-settings`), carregadas de `.env` local.
* `.env.example` lista as variáveis **sem valores reais**: `DATABASE_URL`, `JWT_SECRET`, `BIOMETRIC_KEY`, etc.
* A aplicação **recusa iniciar** em produção se `JWT_SECRET` ou `BIOMETRIC_KEY` estiverem ausentes,
  com o valor de exemplo ou com menos de 32 bytes.
* Nunca registrar em log: senhas, tokens, cookies, imagens, templates biométricos, CPF completo.

---

## 7. Auditoria

Eventos auditados (mínimo):

* autenticação: login, falha, bloqueio, logout, reuso de refresh token;
* usuários, papéis, dispositivos, configurações: criar/alterar/desativar;
* funcionários e jornadas: criar/alterar/ativar/desativar (com antes/depois);
* registros: criado, **rejeitado** (com motivo), ajustado, anulado;
* banco de horas: lançamentos;
* feriados: criar/alterar/excluir;
* biometria: consentimento, cadastro, exclusão, identificação falha (sem imagem e sem template).

A tabela de auditoria é somente inserção (ver `DATABASE.md`).

---

## 8. LGPD

* Dados pessoais tratados: identificação, jornada e — sensível — biometria facial.
* Detalhes de base legal, consentimento, retenção e exclusão da biometria em `BIOMETRICS.md`.
* Funcionário tem acesso aos próprios registros e banco de horas (perfil EMPLOYEE).
* Retenção de registros de ponto: definida pela empresa considerando obrigações trabalhistas
  (pendente de decisão — ver `PROJECT-STATE.md`).
