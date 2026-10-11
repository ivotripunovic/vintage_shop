#!/usr/bin/env bash
#
# Daily traffic report from the nginx access logs, served at /stats/
# (password protected, see deploy/nginx.conf).
#
# Installed by setup.sh to /usr/local/bin and run by /etc/cron.d/goaccess-report.
# Run by hand: sudo /usr/local/bin/goaccess-report.sh
#

set -euo pipefail

OUT_DIR="${OUT_DIR:-/var/www/stats}"

mkdir -p "${OUT_DIR}"
# Write to a temp file and rename, so nobody opens a half-written report
TMP="$(mktemp --suffix=.html "${OUT_DIR}/.report.XXXXXX")"
trap 'rm -f "${TMP}"' EXIT

# All logs logrotate kept (~14 days), gzipped ones included
zcat -f /var/log/nginx/access.log* | goaccess - \
    --log-format=COMBINED \
    --ignore-crawlers \
    --exclude-ip=127.0.0.1 \
    --html-report-title="Vintage Shop traffic" \
    --output="${TMP}"

chmod 644 "${TMP}"
mv -f "${TMP}" "${OUT_DIR}/index.html"
