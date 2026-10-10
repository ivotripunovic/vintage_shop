#!/usr/bin/env bash
# Load test the coming-soon page + waitlist signup on this machine.
#
# Starts gunicorn with the production config (pinned to one CPU core, like the
# 1-CPU VPS) on a throwaway copy of the database, runs locust in stages, and
# reports how many real vs spam signups were saved.
#
# Usage:
#   bash loadtests/run_local.sh                 # coming-soon page (default)
#   bash loadtests/run_local.sh --live          # real homepage (COMING_SOON=False)
#   STAGES="50 200" DURATION=30s bash loadtests/run_local.sh
#   LABEL=after-tuning bash loadtests/run_local.sh

set -euo pipefail

cd "$(dirname "$0")/.."
source venv/bin/activate

COMING_SOON=True
USER_CLASSES=""
if [[ "${1:-}" == "--live" ]]; then
    # No waitlist form once live, so only simulate visitors
    COMING_SOON=False
    USER_CLASSES="Visitor"
fi

STAGES="${STAGES:-50 200 500}"
DURATION="${DURATION:-60s}"
PORT="${PORT:-8001}"
LABEL="${LABEL:-$(date +%Y%m%d-%H%M%S)}"
RESULTS="loadtests/results/${LABEL}"
DB_COPY="${RESULTS}/loadtest.sqlite3"
mkdir -p "$RESULTS"

export DEBUG=True            # SQLite; see the caveat printed below
export SQLITE_PATH="$PWD/$DB_COPY"
export COMING_SOON
export EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend
export WAITLIST_CHECK_DNS=True

cp db.sqlite3 "$DB_COPY"
python manage.py migrate --noinput >/dev/null
python manage.py shell -c "from core.models import WaitlistSubscriber as W; W.objects.filter(email__regex=r'^(loadtest|spam|smartbot)\+').delete()"

echo "Starting gunicorn on 127.0.0.1:${PORT} (1 CPU core, deploy/gunicorn.conf.py)..."
taskset -c 0 gunicorn config.wsgi:application \
    -c deploy/gunicorn.conf.py \
    --bind "127.0.0.1:${PORT}" \
    --access-logfile /dev/null \
    --error-logfile "${RESULTS}/gunicorn.log" &
GUNICORN_PID=$!
trap 'kill $GUNICORN_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
    curl -s -o /dev/null "http://127.0.0.1:${PORT}/" && break
    sleep 0.5
done

for USERS in $STAGES; do
    echo
    echo "=== Stage: ${USERS} concurrent users for ${DURATION} ==="
    locust -f loadtests/locustfile.py --headless \
        --host "http://127.0.0.1:${PORT}" \
        --users "$USERS" --spawn-rate "$(( USERS / 10 > 1 ? USERS / 10 : 1 ))" \
        --run-time "$DURATION" \
        --csv "${RESULTS}/stage-${USERS}" \
        --html "${RESULTS}/stage-${USERS}.html" \
        --only-summary $USER_CLASSES 2>&1 | tail -n 30 || true  # locust exits 1 on any failure
done

echo
echo "=== Spam check (from the load-test database) ==="
python manage.py shell -c "
from django.db.models import Count
from core.models import WaitlistSubscriber as W
real = W.objects.filter(email__startswith='loadtest+').count()
spam = W.objects.filter(email__startswith='spam+').count()
smart = W.objects.filter(email__startswith='smartbot+')
per_ip = dict(smart.values_list('ip_address').annotate(n=Count('id')))
spoofed = [ip for ip in per_ip if not ip.startswith('203.0.113.')]
print(f'Real signups saved:                     {real}')
print(f'Spam saved (must be 0):                 {spam}')
print(f'Smart-bot rows (unconfirmed, never emailed): {smart.count()}')
print(f'  per bot IP (must be <= 5 each):       {per_ip}')
print(f'  stored under a spoofed IP (must be 0): {len(spoofed)}')
"

echo
echo "Reports: ${RESULTS}/stage-*.html (open in a browser)"
echo "Note: this run uses SQLite, which locks on concurrent writes, so signup"
echo "      throughput is lower than production PostgreSQL. Page-view numbers"
echo "      are representative. Nginx's rate limit is not in front of this run."
