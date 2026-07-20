#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

if [ "$(read_env_value ENABLE_HTTPS)" != "true" ]; then
    echo "[ERROR] ENABLE_HTTPS must be true before certificate renewal" >&2
    exit 1
fi

require_command docker
docker compose version >/dev/null

echo "[TLS] Renewing certificates"
compose --profile tls run --rm certbot renew \
    --webroot \
    --webroot-path /var/www/certbot \
    --quiet

echo "[TLS] Reloading Nginx"
compose exec -T nginx nginx -s reload
echo "[TLS] Certificate renewal completed"
