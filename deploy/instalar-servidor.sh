#!/usr/bin/env bash
# Instala o Ponto num servidor Ubuntu 24.04 (VPS), com HTTPS automático. Roda como root:
#   bash instalar-servidor.sh ponto.seudominio.com.br
#
# Antes, envie para a pasta /root do servidor (pelo PC, com o scp):
#   sistema-ponto.zip  (ZIP do GitHub, branch main)         — obrigatório
#   env-do-notebook    (cópia do C:\Ponto\.env)             — para manter os rostos (opcional)
#   ponto-*.dump       (backup mais recente do notebook)    — para trazer os dados (opcional)
# Pode rodar de novo sem medo: o que já existe é mantido.
set -euo pipefail

DOMAIN="${1:?informe o endereço, ex.: bash instalar-servidor.sh restaurante-ponto.duckdns.org}"
DIR=/opt/ponto
cd /root

[ "$(id -u)" -eq 0 ] || { echo "Rode como root."; exit 1; }
[ -f sistema-ponto.zip ] || { echo "Falta /root/sistema-ponto.zip (veja o início deste arquivo)."; exit 1; }

echo "==> 1/7 Pacotes e Docker"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl unzip ufw python3 >/dev/null
if ! command -v docker >/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true

echo "==> 2/7 Memória extra (swap de 4 GB), para a montagem do sistema não faltar memória"
if ! swapon --show | grep -q .; then
    fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 3/7 Arquivos do sistema em $DIR"
mkdir -p "$DIR"
tmp=$(mktemp -d)
unzip -q -o sistema-ponto.zip -d "$tmp"
src=$(find "$tmp" -maxdepth 2 -name docker-compose.prod.yml -printf '%h\n' | head -1)
[ -n "$src" ] || { echo "O ZIP não parece ser do sistema (sem docker-compose.prod.yml)."; exit 1; }
cp -a "$src"/. "$DIR"/   # não mexe em .env nem backups já existentes (não vêm no ZIP)
rm -rf "$tmp"
cd "$DIR"

echo "==> 4/7 Configuração (.env)"
if [ ! -f .env ]; then
    if [ -f /root/env-do-notebook ]; then
        cp /root/env-do-notebook .env
        echo "    usando o .env do notebook (os rostos continuam válidos)"
    else
        cp .env.example .env
        python3 - <<'PY'
import base64, os, re, secrets
text = open(".env").read()
def put(key, value):
    global text
    text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
put("POSTGRES_PASSWORD", secrets.token_urlsafe(32))
put("JWT_SECRET", secrets.token_urlsafe(48))
put("BIOMETRIC_KEY", base64.b64encode(os.urandom(32)).decode())
open(".env", "w").write(text)
PY
        echo "    .env novo criado. GUARDE UMA CÓPIA da linha BIOMETRIC_KEY (fora do servidor):"
        grep '^BIOMETRIC_KEY=' .env
    fi
fi
set_var() {  # set_var NOME valor
    if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}
set_var ENVIRONMENT production
set_var COOKIE_SECURE true
set_var DOMAIN "$DOMAIN"
set_var TLS_MODE public
set_var BACKUP_DIR "$DIR/backups"
set_var BACKUP_KEEP_DAYS 60
sed -i '/^PORT=/d' .env   # a porta do notebook não vale aqui
chmod 600 .env
mkdir -p backups

echo "==> 5/7 Firewall (SSH, 80 e 443)"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "==> 6/7 Montando e ligando o sistema (a primeira vez demora 10 a 20 minutos)"
compose="docker compose -f docker-compose.prod.yml"
$compose up -d --build
for _ in $(seq 1 90); do
    $compose ps backend 2>/dev/null | grep -q healthy && break
    sleep 5
done
$compose ps backend | grep -q healthy || { echo "O backend não ficou saudável. Veja: cd $DIR && $compose logs backend"; exit 1; }

echo "==> 7/7 Dados"
dump=$(ls -t /root/ponto-*.dump 2>/dev/null | head -1 || true)
if [ -n "$dump" ]; then
    cp -n "$dump" backups/
    echo "    restaurando $(basename "$dump")"
    echo RESTAURAR | sh deploy/restore.sh "$(basename "$dump")"
    echo "    Pronto: entre com o seu e-mail e senha de sempre."
else
    echo "    Sem backup para restaurar. Crie o administrador:"
    $compose exec backend python -m app.cli create-admin --email "${ADMIN_EMAIL:-voce@exemplo.com}" --name "${ADMIN_NAME:-Administrador}"
fi

echo
echo "Sistema no ar: https://$DOMAIN/login"
echo "(Se o endereço ainda não abrir, espere 1 a 2 minutos pelo certificado e confira se o DNS aponta para este servidor.)"
