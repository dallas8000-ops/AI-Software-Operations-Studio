#!/bin/sh
set -e
cd /app/backend

PROCESS_TYPE="${PROCESS_TYPE:-web}"

run_collectstatic() {
  echo "Running collectstatic..."
  python manage.py collectstatic --noinput
}

run_migrate() {
  echo "Running migrations..."
  python manage.py migrate --noinput
}

validate_license_if_needed() {
  if [ "${LICENSE_ENFORCEMENT_ENABLED}" = "true" ]; then
    echo "Validating license..."
    python manage.py validate_license_startup
  fi
}

case "$PROCESS_TYPE" in
  web)
    echo "Starting web (Daphne) — PORT=${PORT:-8080}"
    run_collectstatic
    run_migrate
    validate_license_if_needed
    exec daphne -b 0.0.0.0 -p "${PORT:-8080}" config.asgi:application
    ;;
  worker)
    # Prefork defaults to os.cpu_count(), which on Railway reports the HOST's
    # cores, spawning dozens of idle children (~3.2 GB RSS, billed per GB).
    # Cap explicitly; scale with replicas, not hidden host-core fan-out.
    CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"
    CELERY_MAX_MEMORY_PER_CHILD_KB="${CELERY_MAX_MEMORY_PER_CHILD_KB:-200000}"
    echo "Starting Celery worker — concurrency=${CELERY_CONCURRENCY} (scale to N replicas)"
    exec python process_supervisor.py celery -A config worker -l info \
      --concurrency="${CELERY_CONCURRENCY}" \
      --max-memory-per-child="${CELERY_MAX_MEMORY_PER_CHILD_KB}"
    ;;
  beat)
    echo "Starting Celery beat — run exactly ONE replica"
    exec python process_supervisor.py celery -A config beat -l info
    ;;
  transfer-worker)
    echo "Starting API transfer worker (scale to N replicas)"
    exec python manage.py transfer_worker
    ;;
  *)
    echo "Unknown PROCESS_TYPE=${PROCESS_TYPE} (expected web|worker|beat|transfer-worker)"
    exit 1
    ;;
esac
