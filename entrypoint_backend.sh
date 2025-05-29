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

echo "🚀 Starting Daphne server..."
exec daphne -b 0.0.0.0 -p 8000 townlit_b.asgi:application
