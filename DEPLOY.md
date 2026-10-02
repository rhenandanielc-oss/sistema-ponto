# DEPLOY.md

# Instalação em produção

> **Status:** Fase 6. Validado em 2026-10-01 com a pilha completa (`docker-compose.prod.yml`) em modo
> `TLS_MODE=internal`: HTTPS, login, relatórios, kiosk no navegador, backup e restauração.
> Instalação dos terminais: `KIOSK.md`.
> **Um único notebook com Windows (servidor e terminal juntos, sem domínio):** `INSTALACAO-WINDOWS.md`.

---

## 1. O que roda

```
Internet / rede local
        │ 80, 443
┌───────▼────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ caddy          │──▶│ frontend     │──▶│ backend      │──▶│ db           │
│ HTTPS + HSTS   │   │ nginx + SPA  │   │ FastAPI      │   │ PostgreSQL 16│
└────────────────┘   │ CSP          │   │ + biometria  │   └──────▲───────┘
                     └──────────────┘   └──────────────┘          │
                                        ┌──────────────┐   ┌──────┴───────┐
                                        │ scheduler    │   │ backup       │
                                        │ limpeza 24 h │   │ pg_dump 24 h │
                                        └──────────────┘   └──────────────┘
```

* Só o **Caddy** abre portas (80 e 443). Banco, API e frontend ficam numa rede interna do Docker.
* **scheduler:** uma vez por dia roda `python -m app.cli maintenance`. Ele apaga de vez os rostos excluídos há
  mais de 30 dias e limpa tokens do kiosk e sessões vencidas.
* **backup:** um `pg_dump` por dia na pasta `BACKUP_DIR`; apaga os backups com mais de `BACKUP_KEEP_DAYS` dias.

## 2. Requisitos do servidor

| Item | Mínimo |
|---|---|
| Sistema | Linux 64 bits (x86-64) com Docker Engine 24+ e o plugin Docker Compose |
| CPU / memória | 2 vCPU, 4 GB de RAM (reconhecimento facial roda em CPU) |
| Disco | 20 GB + espaço dos backups |
| Relógio | **NTP ativo** (`timedatectl` deve mostrar `System clock synchronized: yes`); o horário da batida é o do servidor |
| Rede | Portas 80 e 443 acessíveis pelos terminais e pelos computadores do administrador |

## 3. Endereço e certificado (HTTPS)

A câmera do kiosk **só funciona em HTTPS**. Escolha uma das opções e preencha no `.env`:

| Situação | `.env` | O que fazer |
|---|---|---|
| Domínio público apontando para o servidor (ex.: `ponto.empresa.com.br`) | `DOMAIN=ponto.empresa.com.br`<br>`TLS_MODE=public` | Abrir as portas 80 e 443 para a internet. O Caddy obtém e renova o certificado do Let's Encrypt sozinho. |
| Só rede local, sem domínio público | `DOMAIN=ponto.local` (ou o IP do servidor)<br>`TLS_MODE=internal` | O Caddy cria uma autoridade certificadora própria. **Instale o certificado raiz dela** em cada terminal e computador do administrador (§3.1). O nome em `DOMAIN` precisa resolver para o servidor (DNS interno ou arquivo `hosts`). |

### 3.1 Certificado raiz no modo `internal`

```sh
docker compose -f docker-compose.prod.yml cp caddy:/data/caddy/pki/authorities/local/root.crt ./ponto-ca.crt
```

* **Windows:** clique duas vezes em `ponto-ca.crt` → Instalar certificado → Máquina local →
  "Autoridades de Certificação Raiz Confiáveis".
* **Linux (Chrome/Chromium):** `sudo cp ponto-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates`.
  O Chrome no Linux usa a própria lista: Configurações → Privacidade e segurança → Segurança →
  Gerenciar certificados → Autoridades → Importar.

O arquivo `ponto-ca.crt` é público (não é segredo). A chave da autoridade fica no volume `caddy-data`.

## 4. Primeira instalação

```sh
git clone <repositório> sistema-ponto && cd sistema-ponto
cp .env.example .env
chmod 600 .env
```

Preencha o `.env`:

| Variável | Como gerar / valor |
|---|---|
| `ENVIRONMENT` | `production` |
| `POSTGRES_PASSWORD` | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `JWT_SECRET` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `BIOMETRIC_KEY` | `python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"` — **guarde uma cópia fora do servidor** (§6.2) |
| `COOKIE_SECURE` | `true` (o `docker-compose.prod.yml` já força) |
| `DOMAIN`, `TLS_MODE` | §3 |
| `BACKUP_DIR`, `BACKUP_KEEP_DAYS` | pasta dos backups (padrão `./backups`) e dias de retenção (padrão 30) |

Suba o sistema e crie o primeiro administrador:

```sh
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # todos "Up"; db e backend "healthy"
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin \
    --email voce@empresa.com.br --name "Seu nome"   # a senha é pedida no terminal
```

Abra `https://DOMAIN/login`. Depois: cadastre os terminais em **Administração → Terminais** e siga o `KIOSK.md`.

A aplicação **recusa iniciar** em produção se `JWT_SECRET` ou `BIOMETRIC_KEY` estiverem vazios, fracos ou com valor
de exemplo — veja `docker compose -f docker-compose.prod.yml logs backend`.

## 5. Atualização

```sh
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrations do banco são aplicadas automaticamente quando o backend inicia. **Faça um backup manual antes**
de atualizar (§6.1).

## 6. Backup e restauração

### 6.1 Banco de dados

* Automático: um arquivo `ponto-AAAAMMDD-HHMMSS.dump` por dia em `BACKUP_DIR` (horário UTC no nome).
* Manual (antes de atualizar, por exemplo):
  ```sh
  docker compose -f docker-compose.prod.yml exec backup sh -c \
    'pg_dump --format=custom --no-owner -h db -U "$POSTGRES_USER" -f /backups/ponto-manual.dump "$POSTGRES_DB"'
  ```
* **Copie os backups para fora do servidor** todos os dias (outro computador, nuvem, disco externo). Um backup que
  fica só no servidor se perde junto com ele. Os arquivos contêm dados pessoais: guarde-os cifrados
  (ex.: `restic`, `gpg`, ou um serviço de backup com criptografia).
* Restaurar (substitui **todos** os dados atuais):
  ```sh
  cp ponto-20261001-030000.dump backups/      # se o arquivo veio de fora
  sh deploy/restore.sh ponto-20261001-030000.dump
  ```
* **Teste a restauração** a cada 3 meses num servidor de teste: um backup nunca restaurado não é confiável.

### 6.2 Chave da biometria (`BIOMETRIC_KEY`)

Os rostos ficam no banco **cifrados** com essa chave, que **não** vai no backup do banco.

* Guarde a chave num cofre de senhas da empresa ou impressa em envelope lacrado, **separada** dos backups.
* Sem a chave, os backups restauram tudo menos os rostos: será preciso cadastrar o rosto de todos de novo.
* Se a chave vazar junto com um backup, os rostos podem ser lidos: troque a chave (§6.3).

### 6.3 Troca da chave da biometria

Ainda não há recifragem automática. Procedimento: gere uma nova chave, troque `BIOMETRIC_KEY` e `BIOMETRIC_KEY_ID`
(ex.: `k2`) no `.env`, reinicie (`up -d`) e recadastre os rostos. Templates da chave antiga deixam de ser lidos
e saem no expurgo após a exclusão.

### 6.4 Outros dados

* `.env`: guarde uma cópia segura (cofre de senhas), junto com a `BIOMETRIC_KEY`.
* Volume `caddy-data`: certificados; no modo `internal` contém a autoridade instalada nos terminais.
  Se perdido, gere de novo e reinstale o certificado raiz (§3.1).

## 7. Operação

| Tarefa | Comando |
|---|---|
| Ver estado | `docker compose -f docker-compose.prod.yml ps` |
| Logs da API (JSON, um evento por linha) | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Saúde | `curl https://DOMAIN/api/v1/health/ready` → `{"status":"ok","database":"ok"}` |
| Último backup | `ls -lt backups/ \| head` e `docker compose -f docker-compose.prod.yml logs backup` |
| Rodar a limpeza agora | `docker compose -f docker-compose.prod.yml exec backend python -m app.cli maintenance` |
| Novo administrador | `docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin ...` |

Os logs registram método, caminho (sem parâmetros), status, duração e IP de cada requisição, com o `request_id`
que também aparece nos erros mostrados ao usuário. Nunca registram senhas, tokens, imagens ou dados biométricos.
O Docker guarda os logs no disco; para limitar o tamanho, configure `log-opts` (`max-size`, `max-file`) no
`/etc/docker/daemon.json`.

## 8. Checklist de produção

- [ ] NTP sincronizado no servidor
- [ ] `.env` com `chmod 600`, segredos gerados como em §4 e cópia segura fora do servidor
- [ ] `https://DOMAIN` abre sem aviso de certificado em todos os terminais
- [ ] Primeiro administrador criado; nenhum usuário de teste
- [ ] Terminais cadastrados e configurados conforme `KIOSK.md`
- [ ] Backup diário aparecendo em `BACKUP_DIR` e **cópia diária para fora do servidor**
- [ ] Restauração testada uma vez
- [ ] Firewall: só 80 e 443 abertas (mais o SSH de administração)
- [ ] Termo de consentimento biométrico assinado por cada funcionário antes do cadastro do rosto (`BIOMETRICS.md`)

## 9. Capacidade medida

Servidor de teste (4 vCPU), 200 funcionários, 2 meses de batidas (34 400 registros):

| Consulta | Tempo |
|---|---|
| Pagamento de 200 funcionários (1 página) | 1,1 s |
| Banco de horas do mês de 200 funcionários (1 página) | 1,6 s (página padrão de 50: 0,5 s) |
| Banco de horas de um funcionário (2 meses) | 25 ms |
| Histórico de batidas do mês (200 por página) | 35 ms |

Os resultados são calculados na hora a partir das batidas (`DATABASE.md` §4). Para milhares de funcionários,
avaliar o cache `daily_summaries` previsto no `DATABASE.md`.
