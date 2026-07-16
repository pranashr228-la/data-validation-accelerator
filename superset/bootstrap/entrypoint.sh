#!/usr/bin/env bash
set -euo pipefail

superset db upgrade

superset fab create-admin \
  --username admin \
  --firstname DVA \
  --lastname Admin \
  --email admin@local \
  --password admin \
  || true

superset init

python /app/bootstrap/import_assets.py
python /app/bootstrap/setup_dashboards.py

exec superset run -h 0.0.0.0 -p 8088 --with-threads
