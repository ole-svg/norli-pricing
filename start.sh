#!/bin/sh
# Norli Pricing Engine startup
echo "Starting Norli Pricing Engine..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
