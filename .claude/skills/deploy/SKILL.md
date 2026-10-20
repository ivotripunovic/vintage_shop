---
name: deploy
description: Production deployment and server ops for vintage_shop. Use when working on deployment, server setup, nginx/gunicorn/systemd config, backups, traffic stats, or any file in deploy/.
---

# Deployment

Production runs on a VPS (Ubuntu 22.04+, 1GB RAM): Gunicorn (Unix socket) → Nginx (reverse proxy + static files) → Let's Encrypt SSL.

## Layout on the server

- App dir: `/srv/django/apps/vintage_shop` (with its own `venv/`, `.env`, `media/`, `staticfiles/`, `logs/`)
- systemd unit: `/etc/systemd/system/vintage_shop.service` (source: `deploy/vintage_shop.service`). It runs as user `django`, group `www-data`.
- Gunicorn config: `deploy/gunicorn.conf.py` (2 workers)
- Nginx config: `deploy/nginx.conf`

## Push-to-deploy (normal path)

`git push production main` → bare repo `/var/repo/vintage_shop.git` → `deploy/hooks/post-receive` does the following:
checkout → pip install → migrate → collectstatic (fails if admin CSS is missing) → restart service → verify it is active.

The hook is copied into the bare repo by `deploy/git-setup.sh`, so edits to `deploy/hooks/post-receive` only take effect after that file is re-copied on the server.

## Scripts

```bash
sudo bash deploy/setup.sh <domain> <db_password>   # initial server setup, once, as root
sudo bash deploy/git-setup.sh                      # bare repo + deploy user + hook, once, after setup.sh
bash deploy/deploy.sh                              # manual deploy (git fetch + reset --hard origin/main)
```

## Crons (installed by setup.sh into /etc/cron.d)

- `backup-db` 03:30: runs `deploy/backup-db.sh`. Writes a pg_dump (last 14 kept), a media mirror and a copy of `.env` to `/var/backups/vintage_shop`, and emails ADMINS on failure. The restore steps are in the script header.
- `goaccess-report` 04:15: runs `deploy/goaccess-report.sh`. Builds a traffic report from the nginx logs, served at `/stats/` (password protected).
- `expire-listings` hourly at :05, as user `django`: runs `manage.py expire_listings`, which marks published products past `expires_at` as expired. Logs to `logs/expire-listings.log`.

## Service management

```bash
sudo systemctl status vintage_shop
sudo systemctl restart vintage_shop
journalctl -u vintage_shop -f
```
