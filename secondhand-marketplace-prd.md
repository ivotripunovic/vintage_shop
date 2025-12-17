# Product Requirements Document: Multi-Vendor Second-Hand Marketplace

## 1. Executive Summary

A monolithic web application that enables multiple sellers to list and sell second-hand items in one centralized marketplace. The platform charges sellers a monthly subscription fee for access to their web shop, with manual payment verification through banking partners.

**Target Launch**: MVP with core features
**Expected Scale at Launch**: 200 sellers, ~2,000 products
**Business Model**: Monthly recurring seller subscriptions

---

## 2. Problem Statement

Fragmented second-hand selling experience. Sellers either:
- Use multiple platforms (eBay, Facebook, local sites) scattered across the web
- Build individual shops (expensive, time-consuming)
- Lack a consolidated customer base

Solution: Provide sellers a single platform with built-in traffic while generating recurring revenue through subscriptions.

---

## 3. Reference: Mercari Model

This app is modeled after **Mercari**, with these similarities:
- Multi-vendor second-hand marketplace
- Structured seller profiles with individual shops
- Product listings with images and condition ratings
- Built-in buyer audience (no need for sellers to drive traffic)
- Mobile-first (our MVP will be web-first)
- Flat fee or commission model (we'll start with subscription)

Key differences from Mercari:
- **Billing**: We use monthly subscriptions for predictable seller costs; Mercari charges per-transaction
- **Payment**: Manual bank verification vs. Mercari's app-based payments
- **Scope**: Local/regional initially vs. Mercari's global

---

## 4. User Personas

### Primary: Sellers
- Age: 25-65
- Tech proficiency: Low to moderate
- Goal: Sell second-hand items with minimal effort, reach buyers without fragmentation
- Pain points: Multiple platforms, inconsistent inventory tracking, payment handling

### Secondary: Buyers
- Age: 18-70
- Tech proficiency: Moderate to high
- Goal: Find quality second-hand items from trusted sellers
- Pain points: Trust, item authenticity, scattered shopping experience

---

## 4. Core Features

### Phase 1 (MVP)

#### Seller Features
- **Authentication & Seller Onboarding**
  - Email registration with verification
  - Seller profile setup (name, description, contact, location)
  - Shop setup (shop name, description, image)
  
- **Inventory Management**
  - Create, edit, delete product listings
  - Product details: title, description, price, category, condition, images (up to 5)
  - Stock tracking (quantity)
  - Draft/publish status
  
- **Seller Dashboard**
  - Sales analytics (orders, revenue overview)
  - Upcoming payment due date
  - Inventory at a glance
  - Recent orders list
  
- **Subscription & Billing**
  - Monthly subscription plan display
  - Payment status (pending, verified, overdue)
  - Invoice history
  - Bank payment instructions

#### Buyer Features
- **Browse & Search**
  - Category browsing
  - Search by keyword, price range, condition
  - Filters (category, seller, price, newest)
  
- **Product Pages**
  - Detailed product view
  - Seller information & shop link
  - Image gallery
  - Similar items (same seller, same category)
  
- **Shopping Cart & Checkout**
  - Add to cart
  - Checkout flow (shipping address, payment method selection)
  - Order summary
  
- **Order Management**
  - View order status
  - Contact seller
  - Order history

#### Admin Features
- **Django Admin Dashboard** (for platform staff)
  - Seller management (approve, suspend, view details)
  - Payment verification & manual approval
  - Invoice generation & tracking
  - Product moderation (flag inappropriate listings)
  - User support (view buyer/seller issues)
  - Site analytics

---

## 5. Technical Requirements

### Tech Stack
- **Framework**: Django 5.2+
- **Database**: PostgreSQL 14+
- **Frontend**: Django Templates + HTMX or React (TBD)
- **API**: Django REST Framework (for future mobile apps)
- **Payment Processing**: Manual bank verification (no API integration in MVP)
- **Authentication**: Django authentication + JWT tokens
- **Hosting**: TBD (AWS, DigitalOcean, etc.)
- **Storage**: Local filesystem or S3 for product images

### Database Schema (Core Entities)
- **User**: email, password, created_at
- **Seller**: user_fk, shop_name, description, location, status
- **SellerSubscription**: seller_fk, plan_type, start_date, end_date, status, amount
- **Product**: seller_fk, title, description, price, category, condition, stock, created_at
- **ProductImage**: product_fk, image_url, order
- **Order**: buyer_fk, created_at, total_price, status
- **OrderItem**: order_fk, product_fk, quantity, price_at_purchase
- **Invoice**: seller_fk, amount, due_date, status, payment_method
- **Payment**: invoice_fk, verified_at, verified_by_admin, amount

### Non-Functional Requirements
- **Performance**: Page load < 2s, support 500 concurrent users
- **Security**: HTTPS, password hashing, CSRF protection, input validation, no PCI compliance needed (no card storage)
- **Scalability**: Should handle 200+ sellers and 10,000+ products without optimization
- **Uptime**: 99.5% availability

---

## 6. Business Requirements

### Billing Model (MVP: Subscription)
- **Current Model**: Monthly subscription
  - **Single tier** for MVP: $9.99/month per seller
  - Charged monthly (1st of month or signup anniversary)
  - Manual payment verification through bank transfer or local processor

- **Payment Flow**
  1. Seller receives invoice via email with bank details
  2. Seller transfers funds to company bank account
  3. Admin staff manually verifies payment in dashboard
  4. Seller receives confirmation email
  5. If overdue (>7 days), shop is marked "suspended" (listings not visible to buyers)

### Billing Model Flexibility (Future Switch Capability)

The platform is designed to support switching between billing models:
1. **Current (MVP)**: Monthly subscription ($9.99/month)
2. **Per-transaction commission**: X% per sale (e.g., 10% like Mercari)
3. **Hybrid**: Monthly base fee + per-transaction commission
4. **Per-listing**: Charge per product listed
5. **Freemium**: Free tier with limited listings, paid tier for unlimited

**Architecture support**: Billing logic is abstracted via a `BillingPlan` model that can store different pricing models. Invoices are generated based on the active billing strategy, so switching is possible with data migration and seller notification.

---

## 7. Success Metrics

- Seller sign-ups & activation rate (target: >60% complete onboarding)
- Monthly recurring revenue (MRR) from subscriptions
- Payment verification time (target: <24 hours)
- Buyer traffic to marketplace
- Average seller retention rate

---

## 8. MVP Scope & Timeline

### Phase 1 (Weeks 1-4): Core Infrastructure
- Django project setup with models
- Database design & migrations
- User authentication (seller & buyer)
- Static pages (landing, about, privacy)

### Phase 2 (Weeks 5-8): Seller Features
- Seller onboarding flow
- Product management CRUD
- Image uploads
- Seller dashboard

### Phase 3 (Weeks 9-11): Buyer Experience
- Product browsing & search
- Shopping cart
- Basic checkout (no payment processing)
- Order tracking

### Phase 4 (Week 12): Admin & Launch Prep
- Admin panel for payment verification
- Invoice generation
- Manual approval workflow
- Testing & deployment

---

## 9. Constraints & Assumptions

### Constraints
- No automated payment processing (manual verification only)
- Limited to bank transfers or local payment processors
- Single language (English)
- No mobile app in MVP

### Assumptions
- Sellers have valid bank accounts for transfers
- Buyers use email for communication
- No international shipping initially
- Trust will be handled through ratings (future feature)
- Sellers are honest about product condition

---

## 10. Out of Scope (Future Features)

- Buyer ratings & reviews
- Seller reputation scoring
- Automated payment processing (Stripe/PayPal integration)
- Commission-based model
- Mobile app
- Real-time chat
- Product recommendations engine
- Multi-language support
- Shipping label integration
