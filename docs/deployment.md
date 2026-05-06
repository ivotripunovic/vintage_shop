# Deployment

Vintage Shop runs on a VPS with Gunicorn + Nginx. Deployments are triggered with a single `git push`.

## How it works

The server holds a **bare git repository** that receives pushes. When you push, a `post-receive` hook fires automatically and:

1. Checks out the new code to `/srv/django/apps/vintage_shop`
2. Creates the Python virtualenv if it doesn't exist yet
3. Installs any new Python dependencies
4. Runs database migrations
5. Collects static files
6. Restarts Gunicorn

```
git push production main
        ↓
bare repo at /var/repo/vintage_shop.git receives push
        ↓
hooks/post-receive fires
        ↓
checkout → pip install → migrate → collectstatic → restart
```

---

## Users and permissions

Two system users are involved:

| User | Role |
|------|------|
| `deploy` | Pushes code, runs the hook, owns files in `/srv/django/apps/vintage_shop` |
| `vintage_shop` | Runs the Gunicorn service, writes application logs |

Both users belong to a shared group **`vsapp`**. The `/srv/django/apps/vintage_shop` directory is owned by `deploy:vsapp` with the setgid bit set, so every file and directory created during a deploy automatically inherits the `vsapp` group and is group-writable. This allows `vintage_shop` to write log files that `deploy` created, and vice versa.

---

## First-time server setup

### Step 1 — Provision the server

Run `setup.sh` once on a fresh Ubuntu 22.04+ VPS as root.

```bash
sudo bash deploy/setup.sh <domain> <db_password>
```

After it finishes, edit `/srv/django/apps/vintage_shop/.env` and fill in any missing values (e.g. `SENDGRID_API_KEY`).

### Step 2 — Enable git push deploys

Run `git-setup.sh` once on the server as root. This:
- Creates the `vsapp` shared group and adds both users to it
- Sets group ownership and permissions on `/srv/django/apps/vintage_shop`
- Creates the bare git repo at `/var/repo/vintage_shop.git`
- Installs the post-receive hook
- Configures sudoers for service restart

```bash
sudo bash deploy/git-setup.sh
```

The script prints the exact `git remote add` command — copy it.

### Step 3 — Add the remote locally

```bash
git remote add production deploy@YOUR_SERVER_IP:/var/repo/vintage_shop.git
```

### Step 4 — First push

```bash
git push production main
```

---

## Deploying

Every deploy is one command:

```bash
git push production main
```

The hook output is streamed to your terminal in real time. A failed step aborts the deploy immediately.

---

## Rollback

```bash
# Force-push an older commit
git push production <commit-sha>:main --force
```

Or on the server directly:

```bash
GIT_DIR=/var/repo/vintage_shop.git GIT_WORK_TREE=/srv/django/apps/vintage_shop git checkout -f <commit-sha>
sudo systemctl restart vintage_shop
```

---

## Service management

```bash
# Application logs (Django)
tail -f /srv/django/apps/vintage_shop/logs/app.log
tail -f /srv/django/apps/vintage_shop/logs/error.log

# Gunicorn / systemd logs
journalctl -u vintage_shop -f

# Restart / status
sudo systemctl restart vintage_shop
sudo systemctl status vintage_shop
```

---

## Updating the hook

The hook lives in the repo at `deploy/hooks/post-receive`. After editing it locally:

```bash
git push production main
sudo cp /srv/django/apps/vintage_shop/deploy/hooks/post-receive /var/repo/vintage_shop.git/hooks/post-receive
sudo chmod +x /var/repo/vintage_shop.git/hooks/post-receive
```

---

## Files

| File | Purpose |
|------|---------|
| `deploy/setup.sh` | One-time server provisioning (run as root) |
| `deploy/git-setup.sh` | One-time bare repo + permissions setup (run as root after setup.sh) |
| `deploy/hooks/post-receive` | Hook that runs on every `git push` |
| `deploy/gunicorn.conf.py` | Gunicorn configuration |
| `deploy/nginx.conf` | Nginx site configuration |
| `deploy/vintage_shop.service` | Systemd service unit |
