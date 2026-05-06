#!/usr/bin/env bash
#
# Initial server setup for Vintage Shop.
# Run once on a fresh Ubuntu 22.04+ VPS as root.
#
# Usage: sudo bash deploy/setup.sh <domain> <db_password>
#

set -euo pipefail

# --- Arguments -----------------------------------------------------------

if [ $# -lt 2 ]; then
    echo "Usage: sudo bash deploy/setup.sh <domain> <db_password>"
    echo "  domain      - Your domain name (e.g. shop.example.com)"
    echo "  db_password - PostgreSQL password for vintage_shop user"
    exit 1
fi

DOMAIN="$1"
DB_PASSWORD="$2"
APP_USER="vintage_shop"
APP_DIR="/srv/django/apps/vintage_shop"
REPO_URL="$(git remote get-url origin 2>/dev/null || echo 'https://github.com/OWNER/vintage_shop.git')"

echo "==> Setting up Vintage Shop on ${DOMAIN}"

# --- 1. System packages --------------------------------------------------

echo "==> Installing system packages..."
apt-get update
apt-get install -y \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib libpq-dev \
    nginx certbot python3-certbot-nginx \
    fail2ban ufw \
    git curl

# --- 2. Firewall ---------------------------------------------------------

echo "==> Configuring UFW firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# --- 3. Create application user ------------------------------------------

echo "==> Creating ${APP_USER} system user..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/bash --group www-data "${APP_USER}"
fi

# --- 4. PostgreSQL --------------------------------------------------------

echo "==> Setting up PostgreSQL database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${APP_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${APP_USER} WITH PASSWORD '${DB_PASSWORD}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_catalog.pg_database WHERE datname='${APP_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${APP_USER} OWNER ${APP_USER};"

# --- 5. Clone repository -------------------------------------------------

echo "==> Cloning repository..."
if [ ! -d "${APP_DIR}" ]; then
    mkdir -p "${APP_DIR}"
    chown "${APP_USER}:www-data" "${APP_DIR}"
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
else
    echo "    Repository already exists, pulling latest..."
    sudo -u "${APP_USER}" git -C "${APP_DIR}" pull origin main
fi

# --- 6. Python virtualenv + dependencies ---------------------------------

echo "==> Setting up Python environment..."
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/venv"
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# --- 7. Production .env ---------------------------------------------------

echo "==> Generating production .env..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

if [ ! -f "${APP_DIR}/.env" ]; then
    cat > "${APP_DIR}/.env" <<ENVEOF
DEBUG=False
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}

DB_NAME=${APP_USER}
DB_USER=${APP_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=127.0.0.1
DB_PORT=5432

SENDGRID_API_KEY=
DEFAULT_FROM_EMAIL=noreply@${DOMAIN}

CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
ENVEOF
    chown "${APP_USER}:www-data" "${APP_DIR}/.env"
    chmod 640 "${APP_DIR}/.env"
    echo "    .env created — edit it to add SENDGRID_API_KEY."
else
    echo "    .env already exists, skipping."
fi

# --- 8. Required directories ---------------------------------------------

echo "==> Creating application directories..."
sudo -u "${APP_USER}" mkdir -p "${APP_DIR}/logs" "${APP_DIR}/media" "${APP_DIR}/static" "${APP_DIR}/staticfiles"

# --- 9. Django migrate + collectstatic ------------------------------------

echo "==> Running Django migrations and collectstatic..."
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/python" "${APP_DIR}/manage.py" migrate --no-input
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/python" "${APP_DIR}/manage.py" collectstatic --no-input --clear
chown -R "${APP_USER}:www-data" "${APP_DIR}/staticfiles"
find "${APP_DIR}/staticfiles" -type d -exec chmod 755 {} +
find "${APP_DIR}/staticfiles" -type f -exec chmod 644 {} +
if [ ! -f "${APP_DIR}/staticfiles/admin/css/base.css" ]; then
    echo "ERROR: Admin static CSS was not collected to ${APP_DIR}/staticfiles/admin/css/base.css"
    exit 1
fi

# --- 10. Systemd service --------------------------------------------------

echo "==> Installing systemd service..."
cp "${APP_DIR}/deploy/vintage_shop.service" /etc/systemd/system/vintage_shop.service
systemctl daemon-reload
systemctl enable vintage_shop
systemctl start vintage_shop

# --- 11. Sudoers for deploy user ------------------------------------------

echo "==> Configuring sudoers for deploys..."
cat > /etc/sudoers.d/vintage_shop <<SUDOEOF
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart vintage_shop
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status vintage_shop
SUDOEOF
chmod 440 /etc/sudoers.d/vintage_shop

# --- 12. SSL certificate --------------------------------------------------

echo "==> Obtaining SSL certificate (before Nginx site config)..."

echo "==> Verifying DNS for ${DOMAIN}..."
if ! getent ahosts "${DOMAIN}" > /dev/null 2>&1; then
    echo "ERROR: ${DOMAIN} does not resolve in DNS yet (NXDOMAIN)."
    echo "Create an A record pointing ${DOMAIN} to this server, then rerun setup."
    exit 1
fi

systemctl stop nginx || true

if ! certbot certonly --standalone -d "${DOMAIN}" --non-interactive --agree-tos \
    --register-unsafely-without-email; then
    echo "ERROR: Certbot failed. Check DNS for ${DOMAIN} and port 80 reachability, then retry."
    exit 1
fi

echo "==> Ensuring Certbot TLS config files exist..."
if [ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]; then
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        -o /etc/letsencrypt/options-ssl-nginx.conf
fi

if [ ! -f /etc/letsencrypt/ssl-dhparams.pem ]; then
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        -o /etc/letsencrypt/ssl-dhparams.pem
fi

# --- 13. Nginx ------------------------------------------------------------

echo "==> Configuring Nginx..."
# Ensure Nginx (www-data) can traverse parent app directories for static/media
chgrp www-data /srv/django /srv/django/apps "${APP_DIR}"
chmod 750 /srv/django /srv/django/apps "${APP_DIR}"

sed "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "${APP_DIR}/deploy/nginx.conf" \
    > "/etc/nginx/sites-available/vintage_shop.conf"

ln -sf /etc/nginx/sites-available/vintage_shop.conf /etc/nginx/sites-enabled/vintage_shop.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl start nginx
systemctl reload nginx

# --- 14. Certbot renewal hooks (standalone safety) ------------------------

echo "==> Installing safe Certbot renewal hooks..."
mkdir -p /etc/letsencrypt/renewal-hooks/pre /etc/letsencrypt/renewal-hooks/post

cat > /etc/letsencrypt/renewal-hooks/pre/10-stop-nginx.sh <<'HOOKPRE'
#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/run/certbot-nginx-running"

if systemctl is-active --quiet nginx; then
    systemctl stop nginx
    touch "${STATE_FILE}"
fi
HOOKPRE
chmod 755 /etc/letsencrypt/renewal-hooks/pre/10-stop-nginx.sh

cat > /etc/letsencrypt/renewal-hooks/post/10-start-nginx.sh <<'HOOKPOST'
#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/run/certbot-nginx-running"

if [ -f "${STATE_FILE}" ]; then
    systemctl start nginx
    rm -f "${STATE_FILE}"
fi
HOOKPOST
chmod 755 /etc/letsencrypt/renewal-hooks/post/10-start-nginx.sh

# --- Done -----------------------------------------------------------------

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Post-setup checklist:"
echo "  1. Edit ${APP_DIR}/.env and add your SENDGRID_API_KEY"
echo "  2. Create a superuser:"
echo "     sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python ${APP_DIR}/manage.py createsuperuser"
echo "  3. Verify the site is running: curl -I https://${DOMAIN}"
echo "  4. Check service status: systemctl status vintage_shop"
echo ""
