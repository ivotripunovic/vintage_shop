# Implementation Plan: Multi-Vendor Second-Hand Marketplace

## 1. Pre-Development: Project Setup & Architecture

### 1.1 Project Structure
```
marketplace/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── config/
│   ├── settings.py (main)
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── users/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── forms.py
│   ├── sellers/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── forms.py
│   ├── products/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   └── forms.py
│   ├── orders/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── signals.py
│   ├── billing/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── tasks.py (for invoice generation)
│   └── core/
│       ├── models.py (base models)
│       ├── views.py (landing, static pages)
│       └── urls.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── sellers/
│   ├── products/
│   ├── orders/
│   └── billing/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── media/ (product images)
├── tests/
│   ├── test_users.py
│   ├── test_sellers.py
│   ├── test_products.py
│   ├── test_orders.py
│   └── test_billing.py
└── scripts/
    └── seed_data.py
```

### 1.2 Technology Decisions
- **Framework**: Django 5.2+
- **Database**: PostgreSQL 14+ with psycopg2
- **ORM**: Django ORM
- **API**: Django REST Framework (for future mobile apps)
- **Frontend**: Django Templates + Tailwind CSS (or Bootstrap)
- **Forms**: Django Forms + django-crispy-forms
- **Image handling**: Pillow + django-storages (for S3 in production)
- **Task queue**: Celery + Redis (for async invoicing)
- **Testing**: pytest + pytest-django
- **Linting**: Black, flake8
- **Environment**: python-decouple or django-environ

---

## 2. Phase 1: Core Infrastructure (Weeks 1-2)

### 2.1 Environment Setup
- [ ] Create Django project: `django-admin startproject config .`
- [ ] Create Django apps: users, sellers, products, orders, billing, core
- [ ] Set up PostgreSQL database
- [ ] Create requirements.txt with core dependencies
- [ ] Set up .env configuration
- [ ] Configure Django settings for development/production/testing
- [ ] Set up Git repository and .gitignore
- [ ] Configure Docker and docker-compose (optional for MVP)

### 2.2 Base Models & Database Schema
Create abstract base models:
- `TimeStampedModel` (created_at, updated_at)
- `SoftDeleteModel` (for soft deletes)

Core models to define:
- [ ] **User**: Email auth, profiles for buyers/sellers
- [ ] **Seller**: Profile, shop info, subscription status, bank details
- [ ] **SellerSubscription**: Start date, end date, plan, status, renewal date
- [ ] **Product**: Title, description, price, category, condition, stock, images
- [ ] **ProductImage**: Product FK, image, order
- [ ] **ProductCategory**: Name, slug, description
- [ ] **Condition**: (New, Like New, Good, Fair) - choice field
- [ ] **Order**: User FK, status, total_price, created_at
- [ ] **OrderItem**: Product FK, Order FK, quantity, price_at_purchase
- [ ] **Invoice**: Seller FK, amount, due_date, status, created_at
- [ ] **Payment**: Invoice FK, verified_at, verified_by, amount
- [ ] **BillingPlan**: Type (subscription, commission, etc.), config (JSON)

### 2.3 User Authentication
- [ ] Custom User model (email as username)
- [ ] User registration (email verification)
- [ ] Login/logout
- [ ] Password reset via email
- [ ] Role-based access (buyer, seller, admin)

### 2.4 Initial Migrations & Testing
- [ ] Create migrations for all models
- [ ] Test database connections
- [ ] Create admin panel configuration for basic models

---

## 3. Phase 2: Seller Features (Weeks 3-5)

### 3.1 Seller Onboarding Flow
- [ ] Registration page (separate from buyer)
- [ ] Email verification
- [ ] Shop setup form (shop name, description, location, profile image)
- [ ] Bank details form (account holder name, IBAN/account number, bank name)
- [ ] Initial subscription creation (set start date, generate first invoice)
- [ ] Redirect to seller dashboard

### 3.2 Seller Models & Permissions
- [ ] Seller model with ForeignKey to User
- [ ] Seller status choices: (active, suspended, banned)
- [ ] Shop verification flag (for future compliance)
- [ ] Seller permissions view (sellers can only edit/view their own data)

### 3.3 Product Management CRUD
- [ ] Create product form (title, description, price, category, condition, stock, images)
- [ ] Image upload (single or multiple)
- [ ] Product listing view (seller's products only)
- [ ] Edit product form
- [ ] Delete product (soft delete or hard)
- [ ] Publish/draft status
- [ ] Search & filter by status, date created

### 3.4 Product Images
- [ ] Image upload handler (Pillow)
- [ ] Image resizing (thumbnail + full size)
- [ ] Storage setup (local for MVP, S3 for production)
- [ ] Image ordering

### 3.5 Seller Dashboard
- [ ] Overview (total products, active products, total sales, MRR)
- [ ] Recent orders widget
- [ ] Subscription status widget (next due date, status)
- [ ] Quick actions (add product, view orders)
- [ ] Account settings (email, password, bank details)

---

## 4. Phase 3: Buyer Features (Weeks 6-8)

### 4.1 Product Browsing
- [ ] Homepage with featured products
- [ ] Product listing page with filters
- [ ] Category pages
- [ ] Search functionality (title, description)
- [ ] Filters: price range, condition, seller, category, date added
- [ ] Sorting: newest, price (asc/desc), popular

### 4.2 Product Detail Page
- [ ] Product images (gallery with zoom)
- [ ] Product info (title, description, price, condition, stock)
- [ ] Seller info (shop name, link to shop profile, seller reviews - future)
- [ ] Related products (same seller, same category)
- [ ] Add to cart button
- [ ] Out of stock message

### 4.3 Shopping Cart
- [ ] Add to cart (store in session or database)
- [ ] View cart
- [ ] Update quantity
- [ ] Remove items
- [ ] Cart persistence (login required or session-based)
- [ ] Cart summary (total items, total price)

### 4.4 Checkout Flow
- [ ] Shipping address form (name, address, phone)
- [ ] Order summary review
- [ ] Place order button
- [ ] Order confirmation (email, page)

### 4.5 Order Management
- [ ] Order list (buyer's orders only)
- [ ] Order detail page (items, seller, status, shipping address)
- [ ] Order status tracking (pending, processing, shipped, delivered)
- [ ] Contact seller link (future feature)

### 4.6 Buyer Authentication
- [ ] Separate buyer registration flow
- [ ] Buyer profile management
- [ ] Order history

---

## 5. Phase 4: Billing & Admin (Weeks 9-11)

### 5.1 Invoice Generation
- [ ] Monthly invoice generation (via Celery task scheduled for 1st of month)
- [ ] Invoice PDF generation
- [ ] Invoice email delivery
- [ ] Invoice storage (database + PDF files)
- [ ] Invoice number generation (format: INV-202501-001)

### 5.2 Admin Dashboard
- [ ] Django admin customization for:
  - Seller management (view, approve, suspend, ban)
  - Invoice management (view, mark as paid, resend)
  - Payment verification (mark invoice as verified)
  - User management (sellers, buyers, staff)
  - Product moderation (flag inappropriate)
  - Order management (view all orders, refunds - future)
- [ ] Payment verification workflow (admin checklist: verify bank transfer, mark invoice paid)
- [ ] Suspension logic (auto-suspend if invoice overdue >7 days)
- [ ] Email templates for payment reminders, confirmations

### 5.3 Billing Models & Logic
- [ ] `Invoice` model (seller, amount, due_date, status, created_at)
- [ ] `Payment` model (invoice, verified_at, verified_by, notes)
- [ ] `BillingPlan` model (plan_type, config JSON for flexible pricing)
- [ ] Invoice status choices: (pending, verified, overdue, cancelled)
- [ ] Monthly invoice generation task (Celery)
- [ ] Overdue detection task (mark invoices overdue after 7 days)
- [ ] Suspension logic (suspend seller if overdue)

### 5.4 Email Templates
- [ ] Invoice email (with bank details, due date, download link)
- [ ] Payment confirmed email
- [ ] Payment overdue reminder (3, 5, 7 days)
- [ ] Suspension notice
- [ ] Reactivation email (when seller pays)

### 5.5 Payment Processor Integration (Manual)
- [ ] Admin form to manually verify payments
- [ ] Bank statement reference field
- [ ] Payment date field
- [ ] Verification notes

---

## 6. Phase 5: Testing & Launch Prep (Weeks 12-13)

### 6.1 Unit & Integration Tests
- [ ] Test seller registration flow
- [ ] Test product CRUD
- [ ] Test shopping cart logic
- [ ] Test order creation
- [ ] Test invoice generation
- [ ] Test billing status updates
- [ ] Test permission checks

### 6.2 End-to-End Tests
- [ ] Seller onboarding → product listing → invoice generation
- [ ] Buyer browsing → add to cart → checkout → order

### 6.3 Security Testing
- [ ] CSRF protection
- [ ] XSS prevention (template escaping)
- [ ] SQL injection prevention (ORM)
- [ ] Authentication & authorization checks
- [ ] Password hashing (PBKDF2)
- [ ] Email verification requirement

### 6.4 Performance Testing
- [ ] Page load times (target: <2s)
- [ ] Database query optimization (N+1 queries)
- [ ] Caching strategy (if needed)

### 6.5 Deployment Prep
- [ ] Dockerfile setup
- [ ] Environment configuration (production secrets)
- [ ] Database backups strategy
- [ ] Static files collection (WhiteNoise or CDN)
- [ ] Email service setup (SMTP or SendGrid)
- [ ] Logging & monitoring setup

---

## 7. Data & Deployment

### 7.1 Seed Data
- [ ] Create fixture files for:
  - Sample categories
  - Sample products (from test sellers)
  - Test users (buyers, sellers)
- [ ] Script for quick database population

### 7.2 Deployment Options
- **Option A**: DigitalOcean App Platform (simplest, $12/month)
- **Option B**: AWS (EC2 + RDS) (scalable but complex)
- **Option C**: Heroku (deprecated but simple alternative)
- **Recommended**: DigitalOcean or Render for MVP

### 7.3 Database Backups
- [ ] Automated daily backups
- [ ] Backup retention policy (30 days)
- [ ] Disaster recovery plan

### 7.4 Monitoring
- [ ] Error tracking (Sentry)
- [ ] Uptime monitoring
- [ ] Application performance monitoring (optional)

---

## 8. Critical Path Dependencies

**Start here:**
1. Project structure & Django setup
2. User models & authentication
3. Seller & Product models
4. Seller onboarding UI
5. Product management UI
6. Buyer browsing UI
7. Orders & checkout
8. Billing & invoicing
9. Admin dashboard
10. Testing & deployment

**Blockers to consider:**
- PostgreSQL must be running before development starts
- Email service (SMTP) needed for testing registration flows
- Image storage (local or S3) needed before product upload feature

---

## 9. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Payment verification becomes bottleneck | High | Build efficient admin UI, automate duplicate invoice prevention |
| Image uploads cause storage issues | Medium | Compress on upload, set size limits, use S3 in production |
| N+1 queries slow down product listing | Medium | Use select_related/prefetch_related in QuerySets |
| Email delivery failures | Medium | Log all emails, use reliable SMTP provider (SendGrid) |
| Seller mistakenly deletes products | Low | Implement soft deletes, add confirmation dialog |
| Database migration issues | High | Test migrations locally, keep rollback strategy |

---

## 10. Next Immediate Actions

1. **This week**: Set up Django project, PostgreSQL, create core models
2. **Next week**: Implement user authentication, seller onboarding
3. **Week 3**: Build product management features
4. **Week 4**: Start buyer features
5. **Weeks 5-6**: Complete buyer flow and testing
6. **Week 7**: Billing system and admin
7. **Week 8**: Final testing, deployment prep, launch

---

## 11. Tools & Commands Quick Reference

```bash
# Project setup
django-admin startproject config .
python manage.py startapp users
python manage.py startapp sellers
python manage.py startapp products
python manage.py startapp orders
python manage.py startapp billing

# Migrations
python manage.py makemigrations
python manage.py migrate

# Run development server
python manage.py runserver

# Create superuser (for admin)
python manage.py createsuperuser

# Run tests
pytest

# Format code
black .
flake8

# Seed data
python manage.py loaddata fixtures/categories.json
```

---

## 12. Open Questions & Decisions

- [ ] Frontend framework: Django templates + Tailwind vs. React?
- [ ] Image storage: Local filesystem or S3?
- [ ] Task queue: Celery + Redis or APScheduler for simpler invoicing?
- [ ] Hosting platform: DigitalOcean, Render, or AWS?
- [ ] Email provider: AWS SES, SendGrid, or SMTP relay?
- [ ] Should sellers be able to edit published products or only drafts?
- [ ] Should products be reviewed by admin before going live?
