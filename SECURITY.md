# SECURITY.md

# Segurança

> **Status:** implementado e revisado (Fase 6, §10). Produção: `DEPLOY.md`. Risco aceito em aberto: anti-spoofing
> (`BIOMETRICS.md` §11).

---

## 1. Perfis de acesso

| Perfil | Como acessa | O que pode fazer |
|---|---|---|
| **Administrador** | `/login` com e-mail e **senha** | Tudo: funcionários, horários, biometria, feriados, histórico, ajustes, banco de horas de todos, dispositivos, configurações, auditoria, outros administradores |
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
* Se reconhecido, o servidor emite um **token de identificação**: aleatório, guardado como hash no banco
  (`kiosk_identifications`), vinculado ao funcionário e ao dispositivo, válido por **60 s**.
* Com esse token o kiosk pode:
  * registrar **uma** batida (o token é consumido);
  * consultar o banco de horas **daquele** funcionário enquanto o token for válido.
* Nenhum endpoint do kiosk aceita id de funcionário vindo do cliente.

---

## 6. Proteção da API

* HTTPS obrigatório em produção: o Caddy (`deploy/Caddyfile`) faz a terminação TLS, redireciona HTTP → HTTPS e envia
  HSTS (1 ano). A câmera do kiosk também exige HTTPS.
* CORS restrito à origem do frontend.
* Limitação de taxa em login, refresh e endpoints do kiosk (`app/core/rate_limit.py`; limites em `API.md`).
  O limitador é em memória, por processo; por isso a API roda com **um** processo uvicorn. O IP considerado é o
  real: o uvicorn usa `--proxy-headers` e só confia no `X-Forwarded-For` vindo da rede interna
  (`FORWARDED_ALLOW_IPS`), e o Caddy substitui o cabeçalho enviado pelo cliente — testado: um `X-Forwarded-For`
  falso diferente a cada tentativa não escapa do limite.
* Tamanho máximo de corpo: 1 MB (`413 PAYLOAD_TOO_LARGE`), checado pelo `Content-Length` na API e pelo
  `client_max_body_size` do nginx (que também cobre envio sem `Content-Length`). Uploads de imagem são lidos com
  limite de 1 MB.
* Imagens: no máximo 4096 × 4096 pixels ao decodificar (`OPENCV_IO_MAX_IMAGE_PIXELS`), contra "bombas" de
  descompressão (§10).
* Documentação interativa (`/api/docs`, OpenAPI) desligada em produção.
* Erros sem stack trace nem SQL (formato em `API.md`).
* Cabeçalhos de segurança em toda resposta da API (`nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`).
* Frontend servido por nginx com **CSP** restritiva (`default-src 'self'`, sem scripts/estilos inline,
  `frame-ancestors 'none'`) e os mesmos cabeçalhos (`frontend/nginx.conf`). A CSP libera só o WebAssembly do
  detector facial do navegador (`'wasm-unsafe-eval'`). `Permissions-Policy` libera a câmera só para o próprio site
  e bloqueia microfone, localização e pagamento.
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
* funcionários e horários: criar/alterar/ativar/desativar (antes/depois);
* registros: criado, **rejeitado** (com motivo), ajustado, anulado;
* consulta do banco de horas no kiosk (funcionário, dispositivo, horário);
* banco de horas: lançamentos;
* feriados;
* biometria: consentimento, cadastro, exclusão, identificação falha (sem imagem e sem template);
* limpeza diária (`system.maintenance`) e expurgo da biometria (`biometric.purged`).

**Imutabilidade garantida pelo banco** (migration `0006`): triggers recusam `UPDATE` e `DELETE` em `audit_logs`,
`time_record_adjustments` e `hour_bank_entries`, e em `time_records` só aceitam anular uma batida ainda não anulada.
Vale mesmo para quem tiver a senha do banco usada pela aplicação; só um `ALTER TABLE ... DISABLE TRIGGER`
explícito (ação de DBA) contornaria.

---

## 9. LGPD

* Dados pessoais: identificação, jornada e — sensível — biometria facial.
* Base legal, consentimento, retenção e exclusão da biometria em `BIOMETRICS.md`.
* O funcionário tem acesso aos próprios dados de ponto pelo kiosk (§5).

---

## 10. Revisão de segurança (Fase 6, 2026-10-01)

| Item verificado | Resultado |
|---|---|
| Dependências Python (`pip-audit`) e npm (`npm audit`) | Nenhuma vulnerabilidade conhecida |
| Todas as rotas administrativas exigem administrador; as do kiosk, terminal | Teste automático lê o OpenAPI e cobre toda rota nova |
| Imagem "bomba" (PNG de 390 KB que vira 20000 × 20000 pixels) | **Corrigido.** Antes ocupava 2,7 GB de memória por requisição (derrubaria o servidor); agora é recusada como `INVALID_IMAGE` antes de alocar |
| Burlar o limite de login com `X-Forwarded-For` falso | Não burla (testado na pilha de produção) |
| Alterar/apagar auditoria, batidas, ajustes, lançamentos direto no banco | Recusado pelo banco (testes em `test_immutable_history.py`) |
| Segredos no Git | Nenhum; `.env`, backups, modelos e arquivos do detector estão no `.gitignore` |
| Segredos fracos em produção | A aplicação não inicia (testes em `tests/unit/test_biometrics.py`) |
| Logs | JSON sem senha, token, query string, imagem ou template (teste automático) |
| Portas expostas em produção | Só 80/443 (Caddy); banco e API só na rede interna |
| Enumeração de e-mail no login | Mesmo custo de tempo e mesma mensagem para e-mail inexistente |

Riscos aceitos e documentados: anti-spoofing do rosto (`BIOMETRICS.md` §8 e §11); limite de requisições em memória
(perde a contagem ao reiniciar; suficiente para um único servidor).
