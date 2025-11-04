#!/bin/bash
set -e

echo "🔍 Waiting for PostgreSQL to be ready..."
# Wait for postgres to be truly ready
sleep 5

echo "🚀 Running database migrations..."
cd /app && alembic upgrade head

echo "✅ Migrations complete. Starting application..."
exec "$@"
