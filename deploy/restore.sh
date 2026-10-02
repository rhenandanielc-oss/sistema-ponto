#!/bin/sh
# Restaura um backup no banco de produção. APAGA os dados atuais do banco.
# Uso (na pasta do projeto, com o sistema no ar):
#   sh deploy/restore.sh ponto-20261001-030000.dump
# Modo de um computador só (docker-compose.local.yml): COMPOSE_FILE=docker-compose.local.yml sh deploy/restore.sh ...
# No Windows use windows\restaurar-backup.cmd.
set -eu

file="${1:?informe o nome do arquivo de backup (ex.: ponto-20261001-030000.dump)}"
compose="docker compose -f ${COMPOSE_FILE:-docker-compose.prod.yml}"

printf 'Isto substitui TODOS os dados atuais pelo backup %s. Digite RESTAURAR para continuar: ' "$file"
read -r answer
[ "$answer" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

$compose stop backend scheduler
$compose exec -T backup sh -c '
    test -f "/backups/$1"
    pg_restore --clean --if-exists --no-owner --exit-on-error \
        -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" "/backups/$1"
' sh "$file"
$compose start backend scheduler
echo "Backup restaurado. Confira o sistema e a Auditoria."
