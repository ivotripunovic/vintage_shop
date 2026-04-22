# Deployment

Vintage Shop runs on a VPS with Gunicorn + Nginx. Deployments are triggered with a single `git push`.

## How it works

The server holds a **bare git repository** that receives pushes. When you push, a `post-receive` hook fires automatically and:

1. Checks out the new code to `/opt/vintage_shop`
2. Installs any new Python dependencies
3. Runs database migrations
4. Collects static files
5. Restarts Gunicorn

```
git push production main
        ↓
bare repo at /home/vintage_shop/repo.git receives push
        ↓
hooks/post-receive fires
        ↓
checkout → pip install → migrate → collectstatic → restart
```

---

## First-time server setup

### Step 1 — Provision the server

Run `setup.sh` once on a fresh Ubuntu 22.04+ VPS as root. This installs all system dependencies, creates the database, configures Nginx, and obtains an SSL certificate.

```bash
sudo bash deploy/setup.sh <domain> <db_password>

# Example:
sudo bash deploy/setup.sh shop.example.com secretpassword
```

After it finishes, edit `/opt/vintage_shop/.env` and fill in any missing values (e.g. `SENDGRID_API_KEY`).

### Step 2 — Enable git push deploys

Run `git-setup.sh` once on the server as root. This creates the bare repo and installs the post-receive hook.

```bash
sudo bash deploy/git-setup.sh
```

The script prints the exact `git remote add` command to run locally — copy it.

### Step 3 — Add the remote locally

On your local machine, run the command printed by `git-setup.sh`:

```bash
git remote add production vintage_shop@YOUR_SERVER_IP:/home/vintage_shop/repo.git
```

### Step 4 — First push

```bash
git push production main
```

You will see the deploy output in your terminal as the hook runs.

---

## Deploying

Every deploy is one command:

```bash
git push production main
```

The hook runs on the server and prints progress. A failed step aborts the deploy and exits with a non-zero code so you can see what went wrong.

---

## Rollback

To roll back to a previous commit:

```bash
# Find the commit you want to roll back to
git log --oneline

# Force-push that commit
git push production <commit-sha>:main --force
```

Or on the server directly:

```bash
cd /opt/vintage_shop
git log --oneline          # find target commit
GIT_DIR=/home/vintage_shop/repo.git GIT_WORK_TREE=/opt/vintage_shop git checkout -f <commit-sha>
sudo systemctl restart vintage_shop
```

---

## Service management

```bash
# View logs
journalctl -u vintage_shop -f

# Check status
sudo systemctl status vintage_shop

# Restart manually
sudo systemctl restart vintage_shop
```

---

## Files

| File | Purpose |
|------|---------|
| `deploy/setup.sh` | One-time server provisioning (run as root) |
| `deploy/git-setup.sh` | One-time bare repo setup (run as root after setup.sh) |
| `deploy/hooks/post-receive` | Hook that runs on every `git push` |
| `deploy/gunicorn.conf.py` | Gunicorn configuration |
| `deploy/nginx.conf` | Nginx site configuration |
| `deploy/vintage_shop.service` | Systemd service unit |

---

## Updating the hook

The hook lives in the repo at `deploy/hooks/post-receive`. After editing it locally, push the change and then re-install it on the server:

```bash
git push production main
sudo cp /opt/vintage_shop/deploy/hooks/post-receive /home/vintage_shop/repo.git/hooks/post-receive
sudo chmod +x /home/vintage_shop/repo.git/hooks/post-receive
```
