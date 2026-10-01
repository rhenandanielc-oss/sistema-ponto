# SECURITY.md

# Segurança

> **Status:** projetado na Fase 0 (revisado em 2026-10-01). Implementação: autenticação do administrador na Fase 1,
> dispositivos na Fase 2, kiosk/biometria na Fase 5, revisão final na Fase 6.

---

## 1. Perfis de acesso

| Perfil | Como acessa | O que pode fazer |
|---|---|---|
| **Administrador** | `/login` com e-mail e **senha** | Tudo: funcionários, carga horária, biometria, feriados, histórico, ajustes, banco de horas de todos, dispositivos, configurações, auditoria, outros administradores |
| **Funcionário** | **Rosto**, no kiosk — sem senha | Registrar a própria batida (escolhendo o tipo) e consultar o **próprio** banco de horas |

Não existem outros perfis. Toda rota administrativa exige administrador autenticado e ativo.

---

## 2. Ameaças consideradas

| Ameaça | Mitigação |
|---|---|
| Funcionário bate ponto por outro | Identificação facial no servidor; auditoria com score e dispositivo; limitações em `BIOMETRICS.md` |
| Funcionário vê o banco de horas de outro | O endpoint do kiosk não recebe id de funcionário: devolve apenas os dados de quem o servidor reconheceu |
| Manipulação do horário | Horário oficial definido pelo servidor |
| Alteração retroativa de registros | Registros imutáveis; ajustes só pelo administrador, com justificativa e auditoria |
| Roubo de sessão do administrador | Access token curto, refresh em cookie `HttpOnly`, rotação com detecção de reuso |
| Força bruta de senha | Bloqueio após falhas + limitação de taxa |
| Kiosk roubado / token vazado | Token de dispositivo revogável e limitado a endpoints do kiosk |
| Vazamento de dados biométricos | Sem imagens armazenadas; templates cifrados; chave fora do banco |
| Segredos no Git | `.env` ignorado; `.env.example` sem valores |

**Risco aceito:** como o funcionário não tem senha, alguém com uma foto/vídeo de um colega poderia tentar enganar a
câmera (ver `BIOMETRICS.md` §8). O impacto na consulta é limitado (somente leitura do banco de horas daquele
funcionário); no registro de ponto, a auditoria permite investigação.

---

## 3. Autenticação do administrador

* Login: `POST /api/v1/auth/login` com e-mail e senha.
* Senhas com **argon2id**; mínimo de 10 caracteres.
* **Access token:** JWT HS256, validade **15 min**, mantido **só em memória** no frontend (nunca em `localStorage`).
* **Refresh token:** aleatório de 256 bits, cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`,
  validade **8 h** (configurável), armazenado como hash, **rotacionado** a cada uso; reuso de token antigo revoga a família.
* Logout revoga o refresh token.
* Administrador desativado: refresh tokens revogados imediatamente.
* **Bloqueio:** 5 falhas consecutivas ⇒ 15 min. Mensagem genérica ("credenciais inválidas").
* Login, falha, bloqueio e logout auditados.
* O primeiro administrador é criado por comando de linha no servidor; não há senha padrão.

### CSRF
Só o refresh token vai por cookie (`SameSite=Strict`, caminho `/auth`); as demais rotas usam o header `Authorization`.

---

## 4. Dispositivo (kiosk)

* O administrador cadastra o terminal e recebe um token aleatório (256 bits) **exibido uma única vez**.
* O kiosk envia `Authorization: Device <token>`; o banco guarda só o hash.
* O token de dispositivo **só** acessa `/api/v1/kiosk/*`. Desativar o dispositivo invalida o token.

## 5. Identificação do funcionário (rosto)

* `POST /kiosk/identify` (com token de dispositivo) recebe um frame, e o **servidor** decide quem é.
* Se reconhecido, o servidor emite um **token de identificação**: aleatório, guardado só em memória do servidor
  (ou como hash no banco), vinculado ao funcionário e ao dispositivo, válido por **60 s**.
* Com esse token o kiosk pode:
  * registrar **uma** batida (o token é consumido);
  * consultar o banco de horas **daquele** funcionário enquanto o token for válido.
* Nenhum endpoint do kiosk aceita id de funcionário vindo do cliente.

---

## 6. Proteção da API

* HTTPS obrigatório em produção (HSTS no proxy). A câmera do kiosk também exige HTTPS.
* CORS restrito à origem do frontend.
* Limitação de taxa em login e endpoints do kiosk.
* Tamanho máximo de corpo: 1 MB.
* Erros sem stack trace nem SQL (formato em `API.md`).
* Cabeçalhos de segurança e CSP no frontend.
* Consultas somente via ORM/parâmetros.

---

## 7. Segredos

* Configuração por variáveis de ambiente, carregadas de `.env` local.
* `.env.example` lista as variáveis **sem valores reais** (`DATABASE_URL`, `JWT_SECRET`, `BIOMETRIC_KEY`, ...).
* A aplicação **recusa iniciar** em produção se `JWT_SECRET` ou `BIOMETRIC_KEY` estiverem ausentes, com valor de
  exemplo ou com menos de 32 bytes.
* Nunca registrar em log: senhas, tokens, cookies, imagens, templates biométricos, CPF completo.

---

## 8. Auditoria

Eventos auditados (mínimo):

* login do administrador: sucesso, falha, bloqueio, logout, reuso de refresh token;
* administradores, dispositivos, configurações: criar/alterar/desativar;
* funcionários e carga horária: criar/alterar/ativar/desativar (antes/depois);
* registros: criado, **rejeitado** (com motivo), ajustado, anulado;
* consulta do banco de horas no kiosk (funcionário, dispositivo, horário);
* banco de horas: lançamentos;
* feriados;
* biometria: consentimento, cadastro, exclusão, identificação falha (sem imagem e sem template).

---

## 9. LGPD

* Dados pessoais: identificação, jornada e — sensível — biometria facial.
* Base legal, consentimento, retenção e exclusão da biometria em `BIOMETRICS.md`.
* O funcionário tem acesso aos próprios dados de ponto pelo kiosk (§5).
