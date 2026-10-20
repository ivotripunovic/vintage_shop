# AGENTS.md

Shared agent instructions for this repository. This is the single source of
truth, read by both Claude Code and opencode; `CLAUDE.md` points here.

## Project Overview

Multi-vendor second-hand marketplace built with Django 5.2 and Python 3.9+. Sellers list vintage/used products, buyers browse and purchase. Uses Django templates with Tailwind CSS (CDN), SQLite for development, PostgreSQL for production.

## Commands

```bash
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

# Linting (isort + black run automatically on edited .py files via project hook)
flake8
black --check .

# Database
python manage.py makemigrations
python manage.py migrate
```

The project's `venv` is auto-activated for shell commands in both tools (surfaced
on `PATH`), so bare `pytest`, `flake8`, `runserver`, etc. work without paths.

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

### Coming Soon Mode

Pre-launch gate in `core.middleware.ComingSoonMiddleware`, toggled by `COMING_SOON` in `.env`. Details: `coming-soon` skill.

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

### Local Tooling Hooks

- `.claude/hooks/format.sh` runs isort + black on `.py` files after edit/write.
  Executed by Claude Code (PostToolUse) and opencode (`.opencode/plugins/venv-format.ts`).
- `.claude/hooks/venv.sh` (Claude Code SessionStart) and the opencode `shell.env`
  plugin hook both surface the project `venv/bin` on `PATH`.

### Tracking Work

- Bugs and feature requests: GitHub Issues, created with `gh issue create` using the templates in `.github/ISSUE_TEMPLATE/`.
- Planned quick todos: `docs/TODO.md`. Link each entry to its issue number once one exists.
- Dated progress notes: `docs/DAILY.md`.

### Deployment

Production: Gunicorn + Nginx on a VPS, push-to-deploy via `deploy/hooks/post-receive`. Details: `deploy` skill and `deploy/`.