#!/usr/bin/env bash
#
# Deploy latest code to production.
# Run as the vintage_shop user.
#
# Usage: bash deploy/deploy.sh
#

set -euo pipefail

APP_DIR="/srv/django/apps/vintage_shop"

cd "${APP_DIR}"

echo "==> Fetching latest code..."
git fetch origin main
git reset --hard origin/main

echo "==> Installing dependencies..."
"${APP_DIR}/venv/bin/pip" install -r requirements.txt

echo "==> Ensuring required directories exist..."
mkdir -p "${APP_DIR}/media" "${APP_DIR}/logs" "${APP_DIR}/static" "${APP_DIR}/staticfiles"

echo "==> Running migrations..."
"${APP_DIR}/venv/bin/python" manage.py migrate --no-input

echo "==> Collecting static files..."
"${APP_DIR}/venv/bin/python" manage.py collectstatic --no-input --clear
find "${APP_DIR}/staticfiles" -type d -exec chmod 755 {} +
find "${APP_DIR}/staticfiles" -type f -exec chmod 644 {} +
if [ ! -f "${APP_DIR}/staticfiles/admin/css/base.css" ]; then
    echo "    ERROR: Admin static CSS missing after collectstatic."
    exit 1
fi

echo "==> Restarting Gunicorn..."
sudo systemctl restart vintage_shop

echo "==> Verifying service..."
sleep 2
if systemctl is-active --quiet vintage_shop; then
    echo "    vintage_shop is running."
else
    echo "    ERROR: vintage_shop failed to start!"
    systemctl status vintage_shop --no-pager
    exit 1
fi

echo "==> Deploy complete."
