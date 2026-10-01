#!/bin/sh
# Backup diário do PostgreSQL (roda no serviço "backup" do docker-compose.prod.yml).
# Formato custom do pg_dump (compactado; restaurável com deploy/restore.sh).
# Os arquivos ficam no volume "backups"; COPIE-OS PARA FORA DO SERVIDOR (DEPLOY.md §6).
set -eu

KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

while :; do
    file="/backups/ponto-$(date -u +%Y%m%d-%H%M%S).dump"
    if pg_dump --format=custom --no-owner --file="$file.partial" -h db -U "$POSTGRES_USER" "$POSTGRES_DB"; then
        mv "$file.partial" "$file"
        echo "backup ok: $file ($(du -h "$file" | cut -f1))"
    else
        rm -f "$file.partial"
        echo "backup FALHOU" >&2
    fi
    find /backups -name 'ponto-*.dump' -mtime +"$KEEP_DAYS" -delete
    sleep "$INTERVAL"
done
