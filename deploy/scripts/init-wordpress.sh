#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

SITE_URL="$(read_env_value WORDPRESS_SITE_URL)"
ADMIN_USER="$(read_env_value WORDPRESS_ADMIN_USER)"
ADMIN_PASSWORD="$(read_env_value WORDPRESS_ADMIN_PASSWORD)"
ADMIN_EMAIL="$(read_env_value WORDPRESS_ADMIN_EMAIL)"

for value_name in SITE_URL ADMIN_USER ADMIN_PASSWORD ADMIN_EMAIL; do
    if [ -z "${!value_name}" ]; then
        echo "[ERROR] Missing WordPress initialization value: $value_name" >&2
        exit 1
    fi
done

wp() {
    compose --profile admin run --rm wp-cli "$@"
}

if ! wp core is-installed >/dev/null 2>&1; then
    wp core install \
        --url="$SITE_URL" \
        --title="钟伟达" \
        --admin_user="$ADMIN_USER" \
        --admin_password="$ADMIN_PASSWORD" \
        --admin_email="$ADMIN_EMAIL" \
        --skip-email
fi

wp plugin activate zwd-portfolio-core
wp theme activate zwd-portfolio
wp zwd seed
wp zwd verify

echo "[WORDPRESS] Initialization and verification completed"
