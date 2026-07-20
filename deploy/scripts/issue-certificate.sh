#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

DOMAIN="$(read_env_value DOMAIN)"
EMAIL="$(read_env_value LETSENCRYPT_EMAIL)"
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "[ERROR] DOMAIN and LETSENCRYPT_EMAIL are required" >&2
    exit 1
fi
if [ "$(read_env_value ENABLE_HTTPS)" = "true" ]; then
    echo "[ERROR] Run certificate issuance while ENABLE_HTTPS=false" >&2
    exit 1
fi

compose up -d nginx
compose --profile tls run --rm certbot \
    certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

echo "[TLS] Certificate issued for $DOMAIN"
echo "[TLS] Set ENABLE_HTTPS=true, WORDPRESS_SITE_URL=https://$DOMAIN,"
echo "[TLS] WORDPRESS_FORCE_SSL_ADMIN=true and CORS_ORIGINS=https://$DOMAIN,"
echo "[TLS] then rerun deploy.sh with the current commit SHA."
