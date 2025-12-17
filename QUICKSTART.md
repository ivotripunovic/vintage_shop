# Vintage Shop - Quick Start Guide

## What's Been Done

✅ **Phase 1: Core Infrastructure (78% Complete)**
- Django project structure created
- 6 Django apps (users, sellers, products, orders, billing, core)
- All core models designed and migrated
- Admin dashboard configured
- Virtual environment with all dependencies installed
- Database set up (SQLite for dev, PostgreSQL-ready for production)

## Getting Started Locally

### 1. Navigate to project
```bash
cd ~/projects/vintage_shop
source venv/bin/activate  # Activate virtual environment
```

### 2. Run development server
```bash
python manage.py runserver
```

Access at: `http://localhost:8000`  
Admin dashboard: `http://localhost:8000/admin/`

### 3. Login to admin
- Email: `admin@vintageshop.local`
- Password: `admin`

## Project Structure

```
vintage_shop/
├── config/              # Django settings & URL routing
├── apps/
│   ├── users/          # User authentication & profiles
│   ├── sellers/        # Seller profiles & subscriptions
│   ├── products/       # Product listings & images
│   ├── orders/         # Orders & order items
│   ├── billing/        # Invoices, payments, billing plans
│   └── core/           # Shared models & utilities
├── templates/          # HTML templates
├── static/            # CSS, JS, images
├── media/             # User uploaded files
├── db.sqlite3         # Development database
└── venv/              # Python virtual environment
```

## Key Features Implemented

### Models
- **User**: Custom user model with email auth, buyer/seller roles
- **Seller**: Shop profiles with bank details, subscription tracking
- **SellerSubscription**: Monthly subscription management
- **Product**: Listings with categories, conditions, images
- **Order & OrderItem**: Shopping cart and order management
- **Invoice & Payment**: Flexible billing with multiple plan types
- **BillingPlan**: Support for subscription, commission, hybrid models

### Admin Features
- Seller management (status, verification, suspension)
- Product management with image uploads
- Order tracking
- Invoice verification workflow
- Payment verification with bank reference tracking

## Next Steps

### Phase 2: Seller Features (Weeks 3-5)
- [ ] Seller registration & onboarding flow
- [ ] Product management UI (CRUD)
- [ ] Image upload functionality
- [ ] Seller dashboard

### Phase 3: Buyer Features (Weeks 6-8)
- [ ] Product browsing & search
- [ ] Shopping cart
- [ ] Checkout flow
- [ ] Order management

### Phase 4: Billing & Admin (Weeks 9-11)
- [ ] Monthly invoice generation (APScheduler)
- [ ] Payment verification workflow
- [ ] Seller suspension logic
- [ ] Email notifications

### Phase 5: Testing & Deployment (Weeks 12-13)
- [ ] Comprehensive testing
- [ ] Production deployment to VPS

## Useful Commands

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Run tests
pytest

# Create superuser
python manage.py createsuperuser

# Shell access (for testing models)
python manage.py shell

# Collect static files (production)
python manage.py collectstatic

# Format code
black .

# Check code quality
flake8
```

## Tech Stack (Final Decision)

- **Backend**: Django 5.2
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Frontend**: Django Templates + Tailwind CSS (CDN)
- **Task Queue**: APScheduler
- **Email**: SendGrid
- **Hosting**: VPS ($5-6/month)
- **Storage**: Local filesystem
- **Cost**: ~$6/month MVP

## Documentation

- [Product Requirements Document](../secondhand-marketplace-prd.md)
- [Implementation Plan](../secondhand-marketplace-implementation-plan.md)
- [Progress Tracker](../secondhand-marketplace-progress.md)
- [Tech Decisions](./TECH_DECISIONS.md)

## Notes

- Database switches automatically from SQLite (dev) to PostgreSQL when `DEBUG=False`
- All models have timestamps (`created_at`, `updated_at`)
- Products support soft deletes (marked as deleted, not removed)
- Seller shops can be suspended/activated via admin
- Invoice payment workflow handles automatic seller suspension for overdue payments

## Current Status

**Phase 1**: 78% complete
- ✅ Project setup
- ✅ All models created
- ✅ Migrations applied
- ✅ Admin configured
- ⏳ Remaining: Auth views (registration, login, password reset)

Ready to start Phase 2 (Seller Features) when you are.
