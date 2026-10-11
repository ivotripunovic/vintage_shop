#!/usr/bin/env bash
#
# Nightly PostgreSQL backup: one compressed dump per day, the last 14 kept.
# Emails ADMINS (from .env) if it fails.
#
# Installed by setup.sh to /usr/local/bin and run by /etc/cron.d/backup-db.
# Run by hand: sudo /usr/local/bin/backup-db.sh
#
# Restore (stop the site first, the dump replaces the current data):
#   sudo systemctl stop vintage_shop
#   sudo -u postgres pg_restore --clean --if-exists -d django /var/backups/vintage_shop/django-<date>.dump
#   sudo systemctl start vintage_shop
#

set -euo pipefail

APP_DIR="/srv/django/apps/vintage_shop"
APP_USER="django"
DB_NAME="${DB_NAME:-django}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/vintage_shop}"
KEEP_DAYS="${KEEP_DAYS:-14}"

notify_failure() {
    (cd "${APP_DIR}" && runuser -u "${APP_USER}" -- venv/bin/python manage.py shell -c \
        "from django.core.mail import mail_admins; mail_admins('Database backup failed', 'Run sudo /usr/local/bin/backup-db.sh on the server to see the error.')") || true
}
trap notify_failure ERR

# Readable by root and the "backup" group, so a user added to that group can
# copy the dumps off the server: sudo usermod -aG backup <your ssh user>
install -d -m 750 -g backup "${BACKUP_DIR}"
umask 027

FILE="${BACKUP_DIR}/${DB_NAME}-$(date +%F).dump"
# Dump to a temp file and rename, so a failed run never leaves a broken dump
runuser -u postgres -- pg_dump --format=custom "${DB_NAME}" > "${FILE}.tmp"
# Fails if the dump is unreadable
pg_restore --list "${FILE}.tmp" > /dev/null
chgrp backup "${FILE}.tmp"
mv -f "${FILE}.tmp" "${FILE}"

find "${BACKUP_DIR}" -name "${DB_NAME}-*.dump" -mtime "+${KEEP_DAYS}" -delete
