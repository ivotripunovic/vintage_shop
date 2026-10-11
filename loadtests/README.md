# Load tests

Simulates launch-day traffic against the coming-soon page and waitlist signup:

| User type    | Share | Behaviour |
|--------------|-------|-----------|
| `Visitor`    | 70%   | Loads `/` every 1–3 s |
| `RealSignup` | 20%   | Loads `/`, "types" for 4–10 s, submits a unique `loadtest+…@gmail.com` |
| `SpamBot`    | 10%   | From 5 IPs: instant submits, filled honeypot, forged timestamp, no CSRF, throwaway / made-up / typo domains, spoofed `X-Forwarded-For`, and "smart" human-like submissions |

## Running

```bash
pip install -r loadtests/requirements.txt

bash loadtests/run_local.sh                        # coming-soon page, 50 → 200 → 500 users
bash loadtests/run_local.sh --live                 # real homepage (COMING_SOON=False)
STAGES="50 200" DURATION=30s LABEL=quick bash loadtests/run_local.sh
```

The script starts gunicorn with `deploy/gunicorn.conf.py`, pinned to **one CPU core** like the VPS, on a throwaway copy of `db.sqlite3`. Reports go to `loadtests/results/<label>/` (gitignored); open `stage-*.html` in a browser.

At the end it checks the database:
- **Spam saved must be 0.** Every bot technique except "smart bot" is rejected outright.
- **Smart-bot rows ≤ 5 per bot IP.** A bot that behaves exactly like a human can only be stopped by the per-IP limit. Its rows stay unconfirmed, so it never gets the launch email.
- **No rows under a spoofed IP.** A fake `X-Forwarded-For` header doesn't change the IP the limit counts.

### Caveats
- Runs on SQLite, which locks on concurrent writes, so signup numbers are pessimistic compared with PostgreSQL. Page-view numbers are representative.
- Nginx isn't in front, so its `limit_req` (10 signups/min per IP) isn't exercised. In production, floods are cut off there before reaching Django.
- A core on a dev machine is usually faster than a VPS vCPU. Treat the numbers as an upper bound and re-run against staging if you have one.

## Profiling a single page

Load tests show *how much* traffic the site handles; the profiler shows *where the time goes* in one request. It renders the page in-process (no gunicorn, no network) on a throwaway copy of `db.sqlite3`:

```bash
python loadtests/profile_page.py                        # coming-soon page
python loadtests/profile_page.py --live                 # real homepage
python loadtests/profile_page.py --path /products/      # any page
python loadtests/profile_page.py --live --filter '^(?!.*venv)'   # project code only
python loadtests/profile_page.py --live --sort tottime --top 40  # hottest functions
```

It prints the time per request, the rough max req/s on one core, every SQL query the page runs (look for repeated near-identical queries, which are N+1 problems), and a cProfile table:
- `--sort cumulative` (default): time including everything a function calls. Read it top-down to find which view, template or tag is expensive.
- `--sort tottime`: time spent inside the function itself. This finds hot spots such as `reverse()` called hundreds of times.

## Testing the live server

### 1. Load test (run from your own machine, not the VPS)
Running locust on the VPS would compete with the site for its one CPU, so run it from your laptop:

```bash
PREVIEW_SECRET=<your COMING_SOON_SECRET> locust -f loadtests/locustfile.py \
    --host https://www.<domain> Visitor \
    --headless -u 50 -r 5 -t 2m --csv loadtests/results/live-50
```

- **`Visitor` only.** `RealSignup` and `SpamBot` refuse to run against a non-local host. They would create real subscribers and send real confirmation emails (hurting your sender reputation), and nginx's per-IP signup limit would block them anyway, since all traffic comes from your single IP. Test signups locally with `run_local.sh`.
- **`PREVIEW_SECRET`** makes visitors use the coming-soon bypass cookie, so they load the real homepage and `/products/`. Without it they get the coming-soon page.
- **Ramp up in steps** (`-u 20`, `50`, `100`, …) and stop when p95 goes above ~1 s or errors appear. Run it off-peak, because real visitors share the same CPU.
- Dropping the trailing `Visitor` and using the web UI (`http://localhost:8089`) lets you watch live charts and stop instantly.

While it runs, watch the server in a second SSH session:

```bash
htop                                 # CPU at 100% on one core = CPU-bound
free -m                              # memory headroom on the 1 GB box
journalctl -u vintage_shop -f        # every request, with its time in ms
sudo tail -f /var/log/nginx/error.log  # 502/504s or limit_req rejections
```

### Signups with valid and invalid emails (test server only)
Never run this against production. On a test server (e.g. `vintage.pufna.com`):

1. **Stop real emails** for the run. In the test server's `.env`, set `EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend`, then `sudo systemctl restart vintage_shop`.
2. **Run all user types from your machine**, with addresses on a domain you own (it needs MX records to pass the DNS check; `pufna.com` has them):
   ```bash
   ALLOW_REMOTE_SIGNUPS=1 LOADTEST_EMAIL_DOMAIN=pufna.com \
   locust -f loadtests/locustfile.py --host https://vintage.pufna.com \
       --headless -u 50 -r 5 -t 2m --csv loadtests/results/test-server
   ```
3. **Check and clean up** on the server:
   ```bash
   cd /srv/django/apps/vintage_shop
   venv/bin/python manage.py shell < loadtests/signup_report.py            # must say PASS
   CLEANUP=1 venv/bin/python manage.py shell < loadtests/signup_report.py  # delete test rows
   ```
4. Restore `EMAIL_BACKEND` in `.env` and restart.

**Expect real signups to be rate limited.** Every simulated user comes from your one public IP, so nginx (10/min) and Django (20 attempts/hour, 5 new signups/day per IP) block most of them with 429s or "Previše pokušaja". In this run, `POST signup (real)` failures are the protection working, not a bug. The run verifies that floods are rejected cheaply, pages stay fast while signups are hammered, and no spam is saved. To also measure signup *throughput*, use `run_local.sh`, or run locust from several machines.

### 2. Find slow pages from real traffic
Gunicorn's access log records how long each request took (`access_log_format` in `deploy/gunicorn.conf.py`). Summarise it on the server:

```bash
journalctl -u vintage_shop --since "1 hour ago" -o cat | venv/bin/python loadtests/slow_requests.py
```

This prints p95, median, max, count and 5xx errors per page (IDs collapsed, so `/products/12/` and `/products/57/` are grouped), slowest first. It works for normal traffic too, not just load tests.

### 3. Profile one page on the server
Once you know which page is slow, see why, using the production PostgreSQL database and settings:

```bash
cd /srv/django/apps/vintage_shop
sudo -u django venv/bin/python loadtests/profile_page.py --server --path /products/ -n 30
```

`--server` uses the database from `.env` as-is (no copy, no migrations). The script only runs GET requests in-process, so it doesn't touch the running site's workers and doesn't write data. Keep `-n` small, because it uses the same CPU as the live site while it runs.

## Results (2026-10-10, 1 core, 60 s per stage)

### Coming-soon page + signups

| Users | Before: req/s | p50 | p95 | After: req/s | p50 | p95 |
|------:|-----:|-----:|-----:|-----:|-----:|-----:|
| 50    | 21   | 12 ms  | 43 ms  | 21   | 10 ms  | 45 ms  |
| 200   | 79   | 32 ms  | 1.0 s  | 81   | 15 ms  | 150 ms |
| 500   | 95 (ceiling) | 2.2 s | 3.8 s | 122 (ceiling) | 1.2 s | 3.3 s |

Spam check in both runs: 0 spam saved, smart bots capped at 5 per IP, 0 rows under spoofed IPs.
At 500 users the server is past capacity, and ~1% of connections were dropped when workers recycled.

### Live homepage (after launch, 30 s per stage)

| Users | Before: req/s | p50 | p95 | After: req/s | p50 | p95 |
|------:|-----:|-----:|-----:|-----:|-----:|-----:|
| 50    | 16 (ceiling) | 680 ms | 2.0 s | 21 | 62 ms | 210 ms |
| 200   | 18 (ceiling) | 6.6 s  | 9.8 s | 35 (ceiling) | 3.0 s | 4.2 s |

## What was changed

1. **Coming-soon form rendered as plain HTML inputs.** Django's widget rendering was half of the page's CPU time (12 → 6 ms per request).
2. **Gunicorn `gthread` workers (2 × 4 threads).** Requests waiting on the database or a DNS check no longer block a whole worker. With sync workers, two slow DNS lookups froze the site.
3. **`max_requests` raised to 5000 with jitter 1000.** At 1000/50, both workers restarted at the same moment every ~25 s under load and dropped queued connections.
4. **Category navigation fragment-cached** (`templates/base.html`). It was rendered three times on every page, with ~100 URL lookups. The cache is cleared whenever a category changes (`core/signals.py`).
5. **Homepage queries cut from ~25 to 4** with `select_related`/`prefetch_related`.
6. **Persistent PostgreSQL connections** (`CONN_MAX_AGE=60`). Not measurable locally on SQLite.
7. **Shared file cache** in production, so both workers share rate-limit counters and DNS results.
8. **Confirmation emails sent in a background thread**, so a slow SMTP server never holds a request.

## Capacity guidance for the 1 GB / 1 vCPU VPS

- **Coming-soon page:** comfortable at ~80 req/s (≈ 200 people actively clicking, or ~4,800 page views per minute) with p95 under 200 ms. The ceiling is ~120 req/s.
- **Live homepage:** comfortable at ~20 req/s, with a ceiling of ~35 req/s (~2,000 page views per minute). This is the tighter limit.
- **Launch day:** the launch email is the biggest spike risk, because everyone clicks at once. Send it in batches, e.g. `python manage.py send_launch_email --limit 300` every 10–15 minutes. For launch week, consider temporarily resizing to 2 vCPU and setting `workers = 4`.
