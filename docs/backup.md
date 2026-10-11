# Backup and restore

The PostgreSQL database is backed up every night on the server. Copy the backups to your own PC as well, because a backup on the same disk as the database is lost together with the server.

---

## What is backed up

| Data | Backed up | Where |
|------|-----------|-------|
| Database (users, shops, products, orders, waitlist) | Nightly at 03:30, last 14 days kept | `/var/backups/vintage_shop/django-<date>.dump` |
| Uploaded images (`media/`) | **No**, see [Media files](#media-files) | `/srv/django/apps/vintage_shop/media/` |
| Code | Not needed, it's in git | |
| `.env` (secrets) | **No**, keep a copy in your password manager | `/srv/django/apps/vintage_shop/.env` |

Each dump is a compressed `pg_dump --format=custom` file. The script checks that the dump is readable before it replaces anything, and emails `ADMINS` (from `.env`) if the backup fails.

---

## How it is set up

`deploy/setup.sh` installs this on a new server. On an existing server, run once:

```bash
cd /srv/django/apps/vintage_shop
sudo install -m 755 deploy/backup-db.sh /usr/local/bin/backup-db.sh
sudo install -m 644 deploy/backup-db.cron /etc/cron.d/backup-db
sudo /usr/local/bin/backup-db.sh
sudo ls -lh /var/backups/vintage_shop
```

Cron runs the copy in `/usr/local/bin`, so root never runs a file the app user can edit. After changing `deploy/backup-db.sh`, re-run the `install -m 755` line.

The folder is readable by root and the `backup` group. To let your SSH user copy the backups (log out and back in afterwards):

```bash
sudo usermod -aG backup <your-ssh-user>
```

---

## Backup by hand

Before a risky deploy (a big migration, a data fix), take a fresh backup and give it a name, because a second run on the same day overwrites that day's file:

```bash
sudo /usr/local/bin/backup-db.sh
sudo cp /var/backups/vintage_shop/django-$(date +%F).dump /var/backups/vintage_shop/django-before-<what>.dump
```

Named copies are deleted after 14 days like the others.

---

## Copy backups to your PC

```bash
mkdir -p ~/backups/vintage_shop
rsync -av <your-ssh-user>@<server>:/var/backups/vintage_shop/ ~/backups/vintage_shop/
```

Without `--delete`, your PC keeps every dump, including those the server has already removed, so you get a longer history.

To copy automatically every day, set up an SSH key (`ssh-copy-id <your-ssh-user>@<server>`), run `crontab -e` on your PC and add:

```
0 9 * * * rsync -a <your-ssh-user>@<server>:/var/backups/vintage_shop/ $HOME/backups/vintage_shop/ >> $HOME/backups/rsync.log 2>&1
```

If the PC is off at 09:00, the next run copies everything it missed.

---

## Restore

### Whole database on the server

This replaces all current data with the dump. Everything written since the dump was taken is lost, so take a backup of the current state first.

```bash
sudo /usr/local/bin/backup-db.sh
sudo cp /var/backups/vintage_shop/django-$(date +%F).dump /var/backups/vintage_shop/django-before-restore.dump

sudo systemctl stop vintage_shop
sudo -u postgres pg_restore --clean --if-exists -d django /var/backups/vintage_shop/django-<date>.dump
sudo systemctl start vintage_shop
curl https://www.<domain>/health/        # should print: ok
```

If the dump is older than the current code, run the migrations after restoring:

```bash
sudo -u django bash -c "cd /srv/django/apps/vintage_shop && venv/bin/python manage.py migrate"
```

### From your PC to the server

```bash
scp ~/backups/vintage_shop/django-<date>.dump <your-ssh-user>@<server>:/tmp/
```

Then restore `/tmp/django-<date>.dump` as above, and delete it from `/tmp` afterwards.

### On a new server

1. Run `deploy/setup.sh` as usual. It creates the empty `django` database and user.
2. Copy the dump to the server and restore it as above.
3. Restore `.env` secrets (`SECRET_KEY` must match the old one, or every user is logged out and email links stop working) and the `media/` folder.

### Only some data

To recover a few rows (for example deleted products), restore into a separate database and copy what you need from there. The live database is not touched:

```bash
sudo -u postgres createdb restore_check
sudo -u postgres pg_restore --no-owner -d restore_check /var/backups/vintage_shop/django-<date>.dump
sudo -u postgres psql restore_check     # look around, copy the rows you need
sudo -u postgres dropdb restore_check
```

---

## Test that backups work

A backup is only proven when it restores. Once a month, on your PC (needs `postgresql` installed):

```bash
createdb vs_restore_test
pg_restore --no-owner -d vs_restore_test ~/backups/vintage_shop/django-<date>.dump
psql vs_restore_test -c "select count(*) from core_waitlistsubscriber"
dropdb vs_restore_test
```

The count should match roughly what the admin shows.

---

## Media files

Uploaded product images are not in the database dump. Before launch there are few of them. Once sellers upload images, pack the folder into the backup folder on the server, so the normal rsync to your PC picks it up:

```bash
sudo tar czf /var/backups/vintage_shop/media-$(date +%F).tar.gz -C /srv/django/apps/vintage_shop media
sudo chgrp backup /var/backups/vintage_shop/media-$(date +%F).tar.gz
```

To restore, copy the archive to the server and unpack it:

```bash
sudo tar xzf /var/backups/vintage_shop/media-<date>.tar.gz -C /srv/django/apps/vintage_shop
sudo chown -R django:www-data /srv/django/apps/vintage_shop/media
```

The nightly backup does not do this yet.

---

## Files

| File | Purpose |
|------|---------|
| `deploy/backup-db.sh` | Dumps the database, keeps 14 days, emails `ADMINS` on failure |
| `deploy/backup-db.cron` | Runs it nightly at 03:30 (installed to `/etc/cron.d/backup-db`) |
