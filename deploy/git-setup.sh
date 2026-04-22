#!/usr/bin/env bash
#
# One-time setup of the bare git repo for push-to-deploy.
# Run on the server after setup.sh, as root.
#
# Usage: sudo bash deploy/git-setup.sh
#

set -euo pipefail

APP_USER="vintage_shop"
APP_DIR="/opt/vintage_shop"
REPO_DIR="/home/${APP_USER}/repo.git"

# --- 1. Create bare repo -------------------------------------------------

echo "==> Creating bare git repo at ${REPO_DIR}..."
mkdir -p "${REPO_DIR}"
git init --bare "${REPO_DIR}"

# --- 2. Install post-receive hook ----------------------------------------

echo "==> Installing post-receive hook..."
cp "${APP_DIR}/deploy/hooks/post-receive" "${REPO_DIR}/hooks/post-receive"
chmod +x "${REPO_DIR}/hooks/post-receive"

# --- 3. Ownership ---------------------------------------------------------

echo "==> Setting ownership..."
chown -R "${APP_USER}:${APP_USER}" "${REPO_DIR}"

# --- 4. Ensure sudoers allows service restart without password -----------
# (setup.sh already adds this, but add it here as a safety net)

if [ ! -f /etc/sudoers.d/vintage_shop ]; then
    echo "==> Adding sudoers entry for service restart..."
    cat > /etc/sudoers.d/vintage_shop <<SUDOEOF
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart vintage_shop
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status vintage_shop
SUDOEOF
    chmod 440 /etc/sudoers.d/vintage_shop
fi

# --- Done -----------------------------------------------------------------

SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=============================="
echo "  Git push deploy is ready!"
echo "=============================="
echo ""
echo "Run these commands on your local machine:"
echo ""
echo "  git remote add production ${APP_USER}@${SERVER_IP}:${REPO_DIR}"
echo "  git push production main"
echo ""
echo "Every future deploy:"
echo "  git push production main"
echo ""
