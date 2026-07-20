#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
BASE_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"
HTTPS_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.https.yml"
ENV_FILE="${ENV_FILE_OVERRIDE:-$DEPLOY_DIR/.env.production}"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Missing environment file: $ENV_FILE" >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    awk -F= -v key="$key" '
        $0 !~ /^[[:space:]]*#/ && $1 == key {
            sub(/^[^=]*=/, "", $0)
            gsub(/\r$/, "", $0)
            print $0
            exit
        }
    ' "$ENV_FILE"
}

COMPOSE_ARGS=(-f "$BASE_COMPOSE_FILE")
if [ "$(read_env_value ENABLE_HTTPS)" = "true" ]; then
    COMPOSE_ARGS+=(-f "$HTTPS_COMPOSE_FILE")
fi
COMPOSE_ARGS+=(--env-file "$ENV_FILE")

compose() {
    docker compose "${COMPOSE_ARGS[@]}" "$@"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "[ERROR] Required command not found: $1" >&2
        exit 1
    fi
}

require_clean_repository() {
    local changes
    changes="$(git -C "$PROJECT_ROOT" status --porcelain --untracked-files=normal)"
    if [ -n "$changes" ]; then
        echo "[ERROR] Repository working tree is not clean:" >&2
        echo "$changes" >&2
        exit 1
    fi
}
