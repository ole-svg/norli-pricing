#!/bin/sh
set -e
echo "Starting Norli Pricing Engine..."
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL is not set"
  exit 1
fi
echo "DATABASE_URL is set. Running migrations..."
python scripts/migrate.py
echo "Migrations complete. Starting FastAPI..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
