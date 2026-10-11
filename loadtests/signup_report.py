"""
Report what a load test's signups left in the database, then optionally
delete them. Run through the Django shell, locally or on a server:

    python manage.py shell < loadtests/signup_report.py
    CLEANUP=1 python manage.py shell < loadtests/signup_report.py

Load-test addresses are recognisable by their prefix: loadtest+ (real users),
spam+ (bots that must all be rejected) and smartbot+ (human-like bots that only
the per-IP limit stops).
"""

import os

from django.db.models import Count

from core.models import WaitlistSubscriber

LOADTEST_REGEX = r"^(loadtest|spam|smartbot)\+"

real = WaitlistSubscriber.objects.filter(email__startswith="loadtest+")
spam = WaitlistSubscriber.objects.filter(email__startswith="spam+")
smart = WaitlistSubscriber.objects.filter(email__startswith="smartbot+")
per_ip = dict(
    smart.values_list("ip_address").annotate(n=Count("id")).order_by("ip_address")
)
# Spoofing bots send a random 10.x.x.x X-Forwarded-For; it must never be stored
spoofed = [ip for ip in per_ip if ip and ip.startswith("10.")]
over_cap = {ip: n for ip, n in per_ip.items() if n > 5}

print(f"Real signups saved:                          {real.count()}")
print(
    f"  of which confirmed:                        {real.filter(confirmed_at__isnull=False).count()}"
)
print(f"Spam saved (must be 0):                      {spam.count()}")
print(f"Smart-bot rows (unconfirmed, never emailed): {smart.count()}")
print(f"  bot IPs over the 5/day cap (must be none): {over_cap or 'none'}")
print(f"  stored under a spoofed IP (must be 0):     {len(spoofed)}")

failed = spam.exists() or over_cap or spoofed
print("RESULT:", "FAIL - spam got through" if failed else "PASS - no spam got through")

if os.environ.get("CLEANUP") == "1":
    deleted, _ = WaitlistSubscriber.objects.filter(email__regex=LOADTEST_REGEX).delete()
    print(f"Deleted {deleted} load-test subscriber(s).")
