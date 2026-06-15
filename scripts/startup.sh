#!/bin/bash
set -e

echo "=== Norli Pricing Engine startup ==="

echo "Koer databasmigrering..."
python scripts/migrate.py

echo "Startar API..."
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
