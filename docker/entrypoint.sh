#!/usr/bin/env bash
set -euo pipefail

# Ensure scripts are executable even if bind mount from host dropped +x
chmod +x docker/*.sh || true

# Optional infra checks are done by compose healthchecks.
# Run migrations / collectstatic on demand (idempotent).
if [[ "${DJANGO_MIGRATE:-0}" == "1" ]]; then
  python manage.py migrate cas_auth --noinput
  python manage.py migrate --noinput
fi

if [[ "${DJANGO_COLLECTSTATIC:-0}" == "1" ]]; then
  python manage.py collectstatic --noinput
fi

# Hand off to the service-specific command (web/worker/beat)
exec "$@"
