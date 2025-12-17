# Technology Stack Decisions

**Project**: Multi-Vendor Second-Hand Marketplace (Vintage Shop)  
**Decision Date**: December 17, 2025  
**Status**: Final (MVP)

---

## Frontend Stack

**Decision**: Django Templates + Tailwind CSS (CDN)

- Use Django server-side rendering with templates
- Tailwind CSS via CDN (no build process)
- HTMX for interactive features (if needed)
- No separate frontend framework (React can be added later)

**Rationale**: Simplest setup for MVP, fastest iteration, zero build complexity

---

## Backend Framework

**Decision**: Django 5.2+

- Monolithic application
- Built-in ORM (Django ORM with PostgreSQL)
- Built-in admin panel
- Built-in authentication system
- Forms and validation included

**Rationale**: Perfect for marketplace with admin-heavy features

---

## Database

**Decision**: PostgreSQL (self-hosted on VPS)

- Not SQLite (concurrent user issues, locking)
- Self-hosted PostgreSQL on same VPS as Django
- Free (no managed database cost)

**Rationale**: SQLite has locking issues with concurrent transactions (multiple checkout + invoice generation). PostgreSQL is free on VPS and production-ready.

---

## Task Queue & Scheduling

**Decision**: APScheduler (Django-compatible)

- Used for monthly invoice generation
- Used for overdue invoice detection
- Runs as background scheduler in same process
- No external Redis/Celery overhead

**Rationale**: MVP only needs simple scheduled tasks (monthly invoices, daily checks). APScheduler runs in-process with zero additional infrastructure.

---

## Hosting

**Decision**: Single VPS (DigitalOcean Droplet or equivalent)

- $4-6/month for basic VPS (1GB RAM, 1 CPU)
- Runs Django + PostgreSQL on same machine
- Deployed with Gunicorn + Nginx
- SSH access for management

**Rationale**: Budget-friendly, simple, sufficient for 200 sellers + 2,000 products, can scale later

---

## Email Service

**Decision**: SendGrid Free Tier

- 100 emails/day free (enough for invoice reminders)
- Reliable delivery
- API integration in Django

**Rationale**: Free tier covers MVP needs, proven reliability

---

## File Storage

**Decision**: Local Filesystem

- Product images stored in `/media` directory
- Served via Nginx static file serving
- No S3 or cloud storage costs

**Rationale**: MVP budget constraints, can migrate to S3 later if needed

---

## Code Quality & Testing

**Decision**: pytest + pytest-django

- Unit tests for models, views, forms
- Integration tests for workflows
- pytest for simple, readable test syntax

**Rationale**: Industry standard for Django testing

---

## Deployment & Version Control

**Decision**: Git + SSH deployment

- GitHub/GitLab for version control
- Deploy via git pull + systemd restart (simple)
- No CI/CD for MVP (can add GitHub Actions later)

**Rationale**: Manual deployment is fast enough for MVP, no overhead

---

## Environment Configuration

**Decision**: .env file with python-decouple

- Sensitive data in .env (not in git)
- Different .env for dev/production
- Version control .env.example

**Rationale**: Security best practice, simple setup

---

## Cost Breakdown (Monthly)

| Item | Cost |
|------|------|
| VPS (Django + PostgreSQL) | $5-6 |
| SendGrid (free tier) | $0 |
| Domain (optional first month) | $12 (annual) |
| **Total** | **~$6/month** |

---

## Future Escalation Path

If MVP succeeds, migration path to:
- Add managed database (DigitalOcean Managed PostgreSQL)
- Add Redis cache layer
- Upgrade to Celery for task queue
- Add S3 for file storage
- Add CDN for static files
- Multi-server setup with load balancer

All without rewriting code—just infrastructure changes.

---

## Decisions NOT Made Yet (Can Defer)

- [ ] Product review workflow (auto-publish or admin-review?)
- [ ] Seller editing published products (allowed or drafts only?)
- [ ] Commission model details (if switching from subscription)
- [ ] Caching strategy (defer until performance issues)
- [ ] Analytics/monitoring tool (defer until MVP launched)
- [ ] Backup strategy specifics (defer until data production)
