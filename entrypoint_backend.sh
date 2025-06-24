#!/bin/sh

DB_HOST=${DB_HOST:-mysql}
DB_PORT=${DB_PORT:-3306}

echo "🕒 Waiting for MySQL at $DB_HOST:$DB_PORT ..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  echo "⏳ Still waiting for MySQL..."
  sleep 2
done

echo "✅ MySQL is up, applying migrations..."
python manage.py migrate

echo "🧹 Collecting static files to: ${STATIC_ROOT}"
python manage.py collectstatic --noinput

echo "🚀 Starting server..."
exec gunicorn townlit_b.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 600 \
  --log-level info
