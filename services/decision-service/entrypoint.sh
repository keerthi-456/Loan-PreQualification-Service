#!/bin/bash
set -e

echo "🔍 Waiting for PostgreSQL to be ready..."
# Wait for postgres and migrations from prequal-api to complete
sleep 10

echo "✅ Starting consumer (migrations handled by prequal-api)..."
exec "$@"
