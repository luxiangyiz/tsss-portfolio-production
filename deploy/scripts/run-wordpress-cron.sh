#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
docker compose version >/dev/null

compose --profile admin run --rm wp-cli cron event run --due-now
