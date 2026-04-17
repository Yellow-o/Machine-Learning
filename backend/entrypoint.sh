#!/bin/sh
set -e

echo "[entrypoint] waiting for database and running migrations..."
RETRIES=30
i=1
while [ "$i" -le "$RETRIES" ]; do
  if python manage.py migrate --noinput; then
    break
  fi
  echo "[entrypoint] migrate failed ($i/$RETRIES), retry in 2s..."
  i=$((i + 1))
  sleep 2
done

if [ "$i" -gt "$RETRIES" ]; then
  echo "[entrypoint] database is not ready after retries, exiting."
  exit 1
fi

python manage.py collectstatic --noinput

echo "[entrypoint] starting django on 0.0.0.0:8000"
python manage.py runserver 0.0.0.0:8000
