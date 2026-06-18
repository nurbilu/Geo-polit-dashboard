#!/usr/bin/env bash
# Single entrypoint shared by web / worker / beat roles.
set -e

ROLE="${1:-web}"

echo "[entrypoint] role=$ROLE"

wait_for() {
  local host="$1" port="$2" name="$3"
  echo "[entrypoint] waiting for $name at $host:$port ..."
  until nc -z "$host" "$port"; do sleep 1; done
  echo "[entrypoint] $name is up."
}

wait_for "${MYSQL_HOST:-db}" "${MYSQL_PORT:-3306}" "MySQL"
wait_for "redis" "6379" "Redis"

case "$ROLE" in
  web)
    echo "[entrypoint] applying migrations + collectstatic"
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput

    # Create the admin superuser non-interactively if credentials are provided.
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
      python manage.py createsuperuser --noinput || true
    fi

    echo "[entrypoint] starting Gunicorn (WSGI)"
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-2}" \
      --threads "${GUNICORN_THREADS:-2}" \
      --timeout 120 \
      --access-logfile - \
      --error-logfile -
    ;;

  worker)
    # RUN_STARTUP_CATCHUP makes apps.ready() queue the backfill from this process only.
    export RUN_STARTUP_CATCHUP=1
    echo "[entrypoint] starting Celery worker (with startup catch-up)"
    exec celery -A config worker \
      --loglevel="${CELERY_LOGLEVEL:-info}" \
      --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;

  beat)
    echo "[entrypoint] starting Celery beat"
    exec celery -A config beat --loglevel="${CELERY_LOGLEVEL:-info}"
    ;;

  *)
    echo "[entrypoint] unknown role '$ROLE', exec-ing as raw command"
    exec "$@"
    ;;
esac
