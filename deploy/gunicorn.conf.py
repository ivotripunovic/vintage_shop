"""
Gunicorn configuration for vintage_shop.
Sizes itself to the server's CPU cores and RAM (PostgreSQL on the same box).
Override with GUNICORN_WORKERS=<n> in the environment.
"""

import multiprocessing
import os

# Bind to Unix socket (Nginx proxies to this)
bind = "unix:/run/vintage_shop/gunicorn.sock"

# Control socket for `gunicornc` (gunicorn 25.1+). The default, ~/.gunicorn/,
# is read-only under the service's ProtectSystem=strict, so keep it next to
# the bind socket in the systemd RuntimeDirectory.
control_socket = "/run/vintage_shop/gunicorn.ctl"


def _cpu_cores():
    # Cores this process may run on (respects taskset/cgroup pinning)
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return multiprocessing.cpu_count()


def _ram_mb():
    try:
        with open("/proc/meminfo") as meminfo:
            for line in meminfo:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 1024


# 2 workers per core, capped by memory: each worker uses ~150MB, and ~600MB
# is left for PostgreSQL, nginx and the OS. Never fewer than 2, so one worker
# restarting doesn't take the site down.
# 1 core / 1GB -> 2 workers, 2 cores / 2GB -> 4, 4 cores / 4GB -> 8.
WORKER_MB = 150
RESERVED_MB = 600
_auto_workers = max(2, min(_cpu_cores() * 2, (_ram_mb() - RESERVED_MB) // WORKER_MB))
workers = int(os.environ.get("GUNICORN_WORKERS") or _auto_workers)

# 4 threads per worker = 4x the concurrent requests for about the same
# memory. Requests spend much of their time waiting (PostgreSQL, DNS checks on
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
