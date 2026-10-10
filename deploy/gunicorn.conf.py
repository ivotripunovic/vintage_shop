"""
Gunicorn configuration for vintage_shop.
Tuned for 1GB RAM / 1 CPU VPS with PostgreSQL on the same box.
"""

import multiprocessing

# Bind to Unix socket (Nginx proxies to this)
bind = "unix:/run/vintage_shop/gunicorn.sock"

# 2 workers — saves ~150MB vs the default (2*CPU+1=3) formula,
# important when PostgreSQL runs on the same 1GB box.
workers = 2

# 4 threads per worker = 8 concurrent requests for roughly the same memory.
# Requests spend much of their time waiting (PostgreSQL, DNS checks on
# waitlist signups), and with sync workers just two slow DNS lookups would
# block the whole site.
worker_class = "gthread"
threads = 4

# Preload for memory savings via copy-on-write on fork
preload_app = True

# Restart workers periodically to cap memory leaks from Pillow/image
# processing. Large jitter keeps the two workers from restarting at the same
# moment; at 1000/50 a traffic spike restarted both together every ~25s,
# dropping queued connections.
max_requests = 5000
max_requests_jitter = 1000

# Timeout for slow requests (image uploads)
timeout = 30
graceful_timeout = 30
keepalive = 5

# Logging — stdout/stderr captured by journald
accesslog = "-"
# Client IP (from nginx), request, status, bytes, and time taken in ms, so
# slow pages show up in `journalctl -u vintage_shop` (see loadtests/slow_requests.py)
access_log_format = '%({x-real-ip}i)s "%(r)s" %(s)s %(b)s %(M)sms'
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "vintage_shop"

# Security — strip proxy headers
forwarded_allow_ips = "127.0.0.1"
