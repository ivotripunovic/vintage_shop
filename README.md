# Vintage Shop - Multi-Vendor Second-Hand Marketplace

Live demo: [https://vintage.pufna.com](https://vintage.pufna.com)

A modern, budget-friendly multi-vendor marketplace for buying and selling second-hand items.

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 14+
- Git

### Installation

1. **Clone and navigate**
```bash
cd ~/projects/vintage_shop
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

5. **Run migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create superuser**
```bash
python manage.py createsuperuser
```

7. **Run development server**
```bash
python manage.py runserver
```

Access at `http://localhost:8000`  
Admin at `http://localhost:8000/admin/`

---

## Project Structure

```
vintage_shop/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── TECH_DECISIONS.md
├── config/           # Django settings
├── apps/             # Django applications
│   ├── users/
│   ├── sellers/
│   ├── products/
│   ├── orders/
│   └── billing/
├── templates/        # HTML templates
├── static/          # CSS, JS, images
├── media/           # User uploads
└── tests/           # Test files
```

---

## Tech Stack

- **Backend**: Django 5.2
- **Database**: PostgreSQL
- **Frontend**: Django Templates + Tailwind CSS
- **Task Queue**: APScheduler
- **Email**: SendGrid
- **Storage**: Local filesystem

---

## Development Commands

```bash
# Run server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run tests
pytest

# Format code
black .

# Check code quality
flake8

# Shell
python manage.py shell
```

---

## Documentation

- [Product Requirements Document](../secondhand-marketplace-prd.md)
- [Implementation Plan](../secondhand-marketplace-implementation-plan.md)
- [Progress Tracker](../secondhand-marketplace-progress.md)
- [Tech Decisions](./TECH_DECISIONS.md)

---

## License

MIT
