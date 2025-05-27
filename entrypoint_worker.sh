#!/bin/sh

DB_HOST=${DB_HOST:-mysql}
DB_PORT=${DB_PORT:-3306}

echo "🕒 Waiting for MySQL at $DB_HOST:$DB_PORT ..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  echo "⏳ Still waiting for MySQL..."
  sleep 2
done

echo "✅ MySQL is up."

# اجرای دستور ورودی (celery یا beat)
exec "$@"
