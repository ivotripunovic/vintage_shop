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

# Preload for memory savings via copy-on-write on fork
preload_app = True

# Restart workers after 1000 requests to prevent memory leaks
# from Pillow/image processing
max_requests = 1000
max_requests_jitter = 50

# Timeout for slow requests (image uploads)
timeout = 30
graceful_timeout = 30
keepalive = 5

# Logging — stdout/stderr captured by journald
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "vintage_shop"

# Security — strip proxy headers
forwarded_allow_ips = "127.0.0.1"
