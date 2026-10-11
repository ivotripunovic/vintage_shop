# Backup and restore

The database, the uploaded images and `.env` are backed up every night on the server. Copy the backups to your own PC as well, because a backup on the same disk as the database is lost together with the server.

---

## What is backed up

| Data | Backed up | Where |
|------|-----------|-------|
| Database (users, shops, products, orders, waitlist) | Nightly at 03:30, last 14 days kept | `/var/backups/vintage_shop/django-<date>.dump` |
| Uploaded images (`media/`) | Nightly, one mirror (see [Media and .env](#media-and-env)) | `/var/backups/vintage_shop/media/` |
| Code | Not needed, it's in git | |
| `.env` (secrets) | Nightly, latest copy | `/var/backups/vintage_shop/env` |

Each dump is a compressed `pg_dump --format=custom` file. The script checks that the dump is readable before it replaces anything, and emails `ADMINS` (from `.env`) if any step fails.

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

The `env` file holds the site's secrets (`SECRET_KEY`, database and email passwords). Anyone in the `backup` group can read it, so add only your own account, and keep the copies on your PC on an encrypted disk.

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

Without `--delete`, your PC keeps every dump, including those the server has already removed, so you get a longer history. The same goes for images: one deleted on the site disappears from the server's mirror the next night but stays on your PC.

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
3. Restore `.env` and `media/` as in [Media and .env](#media-and-env). `SECRET_KEY` must match the old one, or every user is logged out and links in emails already sent stop working.

### Only some data

To recover a few rows (for example deleted products), restore into a separate database and copy what you need from there. The live database is not touched:

```bash
sudo -u postgres createdb restore_check
sudo -u postgres pg_restore --no-owner -d restore_check /var/backups/vintage_shop/django-<date>.dump
sudo -u postgres psql restore_check     # look around, copy the rows you need
sudo -u postgres dropdb restore_check
```

### On your dev PC

Development normally uses SQLite. With `USE_POSTGRES=True` it uses a local PostgreSQL database instead, so you can run the site on a copy of production data. The dump holds real users' emails, so delete it when you're done.

Once, let your user create databases:

```bash
sudo -u postgres createuser --superuser $USER
```

Restore (again whenever you want fresher data):

```bash
dropdb --if-exists vintage_shop_prod
createdb vintage_shop_prod
pg_restore --no-owner --no-privileges -d vintage_shop_prod ~/backups/vintage_shop/django-<date>.dump
```

Run the site on it. Leaving `DB_HOST` empty connects through the local socket as your own user, so no password is needed:

```bash
export USE_POSTGRES=True DB_NAME=vintage_shop_prod DB_USER=$USER DB_HOST=
python manage.py migrate        # only if your local code has newer migrations
python manage.py createsuperuser  # production passwords are not known to you
python manage.py runserver
```

`DEBUG` stays on and email still goes to the console, so nobody gets an email from your PC. To show product images, copy `~/backups/vintage_shop/media/` into the project's `media/` folder.

Run `pytest` in a terminal without these variables. With `USE_POSTGRES=True` set, the tests would use PostgreSQL too.

`pg_restore` must be the same major version as the server's PostgreSQL, or newer. Your PC has 15; check the server with `psql --version`. If the server is newer, install the matching `postgresql-client-<version>` from the [PostgreSQL apt repository](https://www.postgresql.org/download/linux/debian/).

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

## Media and .env

Uploaded images are not in the database dump. Each night the script updates `/var/backups/vintage_shop/media/`, a mirror of the site's `media/` folder (only new and changed files are copied). It also saves the latest `.env` as `/var/backups/vintage_shop/env`.

Restore images on the server:

```bash
sudo rsync -a /var/backups/vintage_shop/media/ /srv/django/apps/vintage_shop/media/
sudo chown -R django:www-data /srv/django/apps/vintage_shop/media
```

Restore `.env` on the server:

```bash
sudo install -m 640 -o django -g www-data /var/backups/vintage_shop/env /srv/django/apps/vintage_shop/.env
sudo systemctl restart vintage_shop
```

From your PC (for example on a new server), copy them up first, then run the commands above with `/tmp/vs-restore/` in place of `/var/backups/vintage_shop/`:

```bash
rsync -av ~/backups/vintage_shop/media ~/backups/vintage_shop/env <your-ssh-user>@<server>:/tmp/vs-restore/
```

Delete `/tmp/vs-restore` afterwards, since it contains the secrets.

---

## Files

| File | Purpose |
|------|---------|
| `deploy/backup-db.sh` | Dumps the database (14 days kept), mirrors `media/`, copies `.env`, emails `ADMINS` on failure |
| `deploy/backup-db.cron` | Runs it nightly at 03:30 (installed to `/etc/cron.d/backup-db`) |
