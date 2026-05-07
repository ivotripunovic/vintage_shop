#!/usr/bin/env bash
#
# One-time setup of the bare git repo for push-to-deploy.
# Run on the server after setup.sh, as root.
#
# Usage: sudo bash deploy/git-setup.sh
#

set -euo pipefail

APP_USER="deploy"
SERVICE_USER="django"
SHARED_GROUP="www-data"
APP_DIR="/srv/django/apps/vintage_shop"
REPO_DIR="/var/repo/vintage_shop.git"
SSH_PORT="22"

# --- 1. Users and shared group --------------------------------------------
# Both the deploy user and the service user join this group so they can
# read/write each other's files in APP_DIR.

echo "==> Ensuring user '${APP_USER}' exists..."
if ! id "${APP_USER}" > /dev/null 2>&1; then
    useradd --system --shell /bin/bash --create-home "${APP_USER}"
    echo "    Created user '${APP_USER}'."
else
    echo "    User '${APP_USER}' already exists."
fi

echo "==> Creating shared group '${SHARED_GROUP}'..."
if ! getent group "${SHARED_GROUP}" > /dev/null 2>&1; then
    groupadd "${SHARED_GROUP}"
fi

echo "==> Adding ${APP_USER} and ${SERVICE_USER} to ${SHARED_GROUP}..."
usermod -aG "${SHARED_GROUP}" "${APP_USER}"
usermod -aG "${SHARED_GROUP}" "${SERVICE_USER}"

# --- 2. Fix APP_DIR ownership and permissions ----------------------------
# setgid (g+s) ensures all new files/dirs inherit SHARED_GROUP automatically.

echo "==> Setting group ownership and permissions on ${APP_DIR}..."
chown -R "${APP_USER}:${SHARED_GROUP}" "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod g+rws {} \;
find "${APP_DIR}" -type f -exec chmod g+rw {} \;

# Ensure logs directory exists and is writable by both users
mkdir -p "${APP_DIR}/logs"
chown "${APP_USER}:${SHARED_GROUP}" "${APP_DIR}/logs"
chmod g+rws "${APP_DIR}/logs"

# Ensure Nginx can traverse app directories and read static assets
chmod o+rx /srv/django /srv/django/apps "${APP_DIR}"
mkdir -p "${APP_DIR}/staticfiles"
find "${APP_DIR}/staticfiles" -type d -exec chmod o+rx {} \;
find "${APP_DIR}/staticfiles" -type f -exec chmod o+r {} \;

# --- 3. Create bare repo --------------------------------------------------

echo "==> Creating bare git repo at ${REPO_DIR}..."
mkdir -p "$(dirname "${REPO_DIR}")"
git init --bare "${REPO_DIR}"

# --- 4. Install post-receive hook -----------------------------------------

echo "==> Installing post-receive hook..."
cp "${APP_DIR}/deploy/hooks/post-receive" "${REPO_DIR}/hooks/post-receive"
chmod +x "${REPO_DIR}/hooks/post-receive"
chown -R "${APP_USER}:${APP_USER}" "${REPO_DIR}"

# --- 5. Sudoers -----------------------------------------------------------

echo "==> Configuring sudoers for service restart..."
cat > /etc/sudoers.d/vintage_shop <<SUDOEOF
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart vintage_shop
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status vintage_shop
SUDOEOF
chmod 440 /etc/sudoers.d/vintage_shop

# --- Done -----------------------------------------------------------------

SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=============================="
echo "  Git push deploy is ready!"
echo "=============================="
echo ""
echo "Run these commands on your local machine:"
echo ""
echo "  git remote add production ssh://${APP_USER}@${SERVER_IP}:${SSH_PORT}${REPO_DIR}"
echo "  git push production main"
echo ""
echo "NOTE: Log out and back in as ${APP_USER} for group membership to take effect."
echo ""
