# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-vendor second-hand marketplace built with Django 5.2 and Python 3.9+. Sellers list vintage/used products, buyers browse and purchase. Uses Django templates with Tailwind CSS (CDN), SQLite for development, PostgreSQL for production.

## Commands

```bash
# Activate virtual environment (required before all commands)
source venv/bin/activate

# Run development server
python manage.py runserver

# Run all tests (parallel by default via pytest-xdist)
pytest

# Run tests excluding slow view tests
pytest -m "not slow"

# Run a single test file
pytest users/test_forms.py

# Run a single test
pytest users/test_forms.py::TestClassName::test_method_name

# Run with coverage
pytest --cov

# Code formatting and linting
black .
black --check .
flake8
isort .

# Database
python manage.py makemigrations
python manage.py migrate
```

## Architecture

### Django Apps

- **config/** - Project settings, root URL conf, WSGI/ASGI. Database auto-switches: SQLite when `DEBUG=True`, PostgreSQL otherwise.
- **users/** - Custom `User` model (`AUTH_USER_MODEL = "users.User"`) with email-based auth. `is_buyer`/`is_seller` role flags. `VerificationToken` for email verification and password reset with expiration.
- **sellers/** - `Seller` (OneToOne with User) for shop profiles. `SellerSubscription` for billing. Post-save signal (`sellers/signals.py`) auto-creates Seller profile + subscription when User with `is_seller=True` is created.
- **products/** - `Product` (soft-deletable), `ProductImage` (multiple per product, ordered), `ProductCategory`, `ProductCondition`. Products have status workflow: draft → published → sold/archived.
- **orders/** - `Order` + `OrderItem`. OrderItem captures price at purchase time.
- **billing/** - `Invoice`, `Payment` (OneToOne with Invoice), `BillingPlan` (uses JSONField for flexible config supporting subscription/commission/hybrid/per-listing/freemium models).
- **core/** - Abstract base models: `TimeStampedModel` (created_at/updated_at) and `SoftDeleteModel` (extends TimeStamped with is_deleted/deleted_at + soft_delete()/restore() methods).

### URL Structure

URLs use i18n patterns with language prefix (Serbian default, English secondary). `USE_I18N = False` in settings but locale middleware and i18n URL patterns are active.

- `/auth/` - users app (register, login, verify-email, password-reset)
- `/seller/` - sellers app (register, dashboard, shop pages, product management)
- `/products/` - products app (browse, create, edit, images)
- `/admin/` - Django admin (non-i18n)

### Key Patterns

- **Soft deletes**: Products use `SoftDeleteModel` — call `soft_delete()` instead of `delete()`.
- **Signal-driven seller creation**: Creating a User with `is_seller=True` automatically creates a Seller profile and initial SellerSubscription via post_save signal.
- **Environment config**: Uses `python-decouple` — settings read from `.env` file (see `.env.example`).
- **Forms**: Use django-crispy-forms with Tailwind template pack.
- **Email**: Console backend in development, SendGrid in production.

### Testing

- pytest with pytest-django. Config in `pytest.ini`, test settings in `config/settings_test.py`.
- View tests (`test_views.py` files) are auto-marked as `slow` by `conftest.py`.
- Tests run in parallel (`-n auto`) with `--reuse-db` for speed.
- Test settings use MD5 password hasher (~100x faster), in-memory cache, logging disabled.

### Deployment

Production runs on a VPS with Gunicorn + Nginx on Ubuntu 22.04+. Scripts live in `deploy/`.

- **Stack**: Gunicorn (Unix socket) → Nginx (reverse proxy + static files) → Let's Encrypt SSL
- **Service**: systemd unit at `/etc/systemd/system/vintage_shop.service`, runs as `vintage_shop` user
- **Config**: `deploy/gunicorn.conf.py` (2 workers, tuned for 1GB RAM VPS)

```bash
# Initial server setup (run once as root)
sudo bash deploy/setup.sh <domain> <db_password>

# Routine deployment (run as vintage_shop user)
bash deploy/deploy.sh

# Service management
sudo systemctl status vintage_shop
sudo systemctl restart vintage_shop
journalctl -u vintage_shop -f   # view logs
```
