#!/bin/bash
set -e

# ==============================
# CONFIGURE THESE
# ==============================

ADMIN_USER="ivo"
SSH_PORT="2222"
PUBLIC_KEY="PASTE_YOUR_PUBLIC_KEY"
DJANGO_USER="django"
POSTGRES_VERSION="17"

# ==============================
# UPDATE SYSTEM
# ==============================

apt update && apt upgrade -y
apt install sudo ufw fail2ban unattended-upgrades \
nginx postgresql redis-server \
python3-venv python3-pip \
curl vim -y

# ==============================
# CREATE ADMIN USER
# ==============================

if ! id "$ADMIN_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" $ADMIN_USER
    usermod -aG sudo $ADMIN_USER
fi

mkdir -p /home/$ADMIN_USER/.ssh
echo "$PUBLIC_KEY" > /home/$ADMIN_USER/.ssh/authorized_keys
chmod 700 /home/$ADMIN_USER/.ssh
chmod 600 /home/$ADMIN_USER/.ssh/authorized_keys
chown -R $ADMIN_USER:$ADMIN_USER /home/$ADMIN_USER/.ssh

# ==============================
# CREATE DJANGO SYSTEM USER
# ==============================

if ! id "$DJANGO_USER" &>/dev/null; then
    adduser --system --group --home /srv/django $DJANGO_USER
fi

mkdir -p /srv/django/apps
chown -R $DJANGO_USER:$DJANGO_USER /srv/django

# ==============================
# HARDEN SSH
# ==============================

SSHD_CONFIG="/etc/ssh/sshd_config"
cp $SSHD_CONFIG ${SSHD_CONFIG}.backup

sed -i "s/^#*PermitRootLogin.*/PermitRootLogin no/" $SSHD_CONFIG
sed -i "s/^#*PasswordAuthentication.*/PasswordAuthentication no/" $SSHD_CONFIG
sed -i "s/^#*Port.*/Port $SSH_PORT/" $SSHD_CONFIG

if ! grep -q "AllowUsers $ADMIN_USER" $SSHD_CONFIG; then
    echo "AllowUsers $ADMIN_USER" >> $SSHD_CONFIG
fi

systemctl restart ssh

# ==============================
# FIREWALL
# ==============================

ufw default deny incoming
ufw default allow outgoing

ufw allow $SSH_PORT/tcp
ufw allow 80
ufw allow 443

ufw --force enable

# ==============================
# FAIL2BAN
# ==============================

cat <<EOF > /etc/fail2ban/jail.local
[sshd]
enabled = true
port = $SSH_PORT
maxretry = 3
bantime = 1h
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# ==============================
# POSTGRES HARDENING
# ==============================

PG_CONF="/etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf"
PG_HBA="/etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf"

sed -i "s/^#*listen_addresses.*/listen_addresses = 'localhost'/" $PG_CONF

cat <<EOF > $PG_HBA
local   all             postgres                                peer
local   all             all                                     peer
host    all             all             127.0.0.1/32            scram-sha-256
EOF

systemctl restart postgresql

# ==============================
# REDIS HARDENING
# ==============================

REDIS_CONF="/etc/redis/redis.conf"

sed -i "s/^bind .*/bind 127.0.0.1 ::1/" $REDIS_CONF
sed -i "s/^protected-mode .*/protected-mode yes/" $REDIS_CONF
sed -i "s/^# requirepass .*/requirepass CHANGE_THIS_REDIS_PASSWORD/" $REDIS_CONF

systemctl restart redis-server

# ==============================
# AUTO SECURITY UPDATES
# ==============================

dpkg-reconfigure -f noninteractive unattended-upgrades

# ==============================
# SYSCTL HARDENING
# ==============================

cat <<EOF >> /etc/sysctl.conf

# Hardening
net.ipv4.conf.all.rp_filter=1
net.ipv4.icmp_echo_ignore_broadcasts=1
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.all.accept_redirects=0
net.ipv4.tcp_syncookies=1
EOF

sysctl -p

# ==============================
# FILE PERMISSIONS BASELINE
# ==============================
#
# Nginx runs as www-data and must be able to traverse these parent
# directories to serve app static files from /srv/django/apps/*/staticfiles.
# Keep owner as django, but grant group execute/read to www-data.

chgrp www-data /srv/django /srv/django/apps
chmod 750 /srv/django /srv/django/apps

# ==============================
# DONE
# ==============================

echo "======================================"
echo "SECURE MULTI-DJANGO SERVER READY"
echo "SSH: ssh $ADMIN_USER@server_ip -p $SSH_PORT"
echo "Apps directory: /srv/django/apps"
echo "======================================"
