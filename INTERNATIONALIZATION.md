# Internationalization (i18n) Guide

This document explains how to add and manage translations for the Vintage Shop marketplace.

## Supported Languages

Currently, the following languages are configured:
- **Serbian** (sr) - Default / Primary
- **English** (en) - Secondary

Users can switch languages using the language selector (🌐) in the navigation menu.

---

## How to Add Translations

### Step 1: Mark Strings as Translatable

In your **Python code** (views, models, forms):

```python
from django.utils.translation import gettext_lazy as _

# Mark strings
title = _("Seller Dashboard")
description = _("Manage your products and account")
```

In your **HTML templates**:

```html
{% load i18n %}
<h1>{% trans "Welcome to Vintage Shop" %}</h1>
<p>{% blocktrans %}Hello {{ user.email }}{% endblocktrans %}</p>
```

### Step 2: Create Translation Files

Extract translatable strings from the codebase:

```bash
python manage.py makemessages -l es  # Create Spanish messages
python manage.py makemessages -l fr  # Create French messages
python manage.py makemessages -a     # Create for all languages
```

This creates `.po` files in `locale/LANGUAGE/LC_MESSAGES/django.po`

### Step 3: Translate the Strings

Edit the `.po` file for each language. Example for `locale/es/LC_MESSAGES/django.po`:

```po
msgid "Seller Dashboard"
msgstr "Panel de Vendedor"

msgid "Manage your products and account"
msgstr "Administra tus productos y cuenta"
```

### Step 4: Compile Translations

Convert `.po` files to binary `.mo` files:

```bash
python manage.py compilemessages
```

### Step 5: Restart the Server

```bash
python manage.py runserver
```

---

## File Structure

```
vintage_shop/
├── locale/
│   ├── es/
│   │   └── LC_MESSAGES/
│   │       ├── django.po      # Spanish translations (human-readable)
│   │       └── django.mo      # Spanish translations (compiled)
│   ├── fr/
│   │   └── LC_MESSAGES/
│   │       ├── django.po
│   │       └── django.mo
│   └── ...
├── templates/
│   └── base.html  # Uses {% trans %} and {% blocktrans %} tags
└── ...
```

---

## Example: Translating a View

### Python Code (views.py)

```python
from django.utils.translation import gettext_lazy as _

def seller_dashboard_view(request):
    messages.success(request, _('Welcome to your dashboard'))
    # ... rest of code
```

### Template (dashboard.html)

```html
{% load i18n %}

<h1>{% trans "Seller Dashboard" %}</h1>
<p>{% trans "Manage your products and account" %}</p>

{% blocktrans with shop_name=seller.shop_name %}
    Welcome to {{ shop_name }}!
{% endblocktrans %}
```

### Spanish Translation (locale/es/LC_MESSAGES/django.po)

```po
msgid "Seller Dashboard"
msgstr "Panel del Vendedor"

msgid "Manage your products and account"
msgstr "Administra tus productos y cuenta"

msgid "Welcome to your dashboard"
msgstr "Bienvenido a tu panel"
```

---

## Language Switcher UI

### Desktop
- Appears as a dropdown button in the top-right navigation
- Shows: `🌐 EN` (or current language code)
- Click to see available languages

### Mobile
- Appears in the hamburger menu
- Language options listed in a section
- Tap language name to switch

### How It Works
When a user selects a language:
1. Django sets the user's language preference
2. Next page load displays content in selected language
3. Language choice persists via browser cookies/session

---

## Key Django i18n Features Used

1. **LocaleMiddleware** - Automatically detects user language from:
   - URL prefix (e.g., `/es/dashboard/`)
   - Cookie (`django_language`)
   - Session
   - Accept-Language header

2. **i18n URL patterns** - URLs are automatically prefixed with language code:
   - `/en/dashboard/` → English version
   - `/es/dashboard/` → Spanish version
   - `/fr/dashboard/` → French version

3. **Translation tags in templates**:
   - `{% trans "string" %}` - Simple strings
   - `{% blocktrans %}...{% endblocktrans %}` - Complex strings with variables

4. **gettext_lazy()** - Marks strings for translation in Python code

---

## Common Commands

```bash
# Create translation files for Spanish
python manage.py makemessages -l es

# Create translation files for all configured languages
python manage.py makemessages -a

# Compile all translation files to binary format
python manage.py compilemessages

# Check for missing translations
python manage.py compilemessages --locale es

# Create translations with specific locale paths
python manage.py makemessages -l es -i venv
```

---

## Best Practices

1. **Mark strings early** - Use `_()` and `{% trans %}` from the start
2. **Use clear, simple strings** - Helps translators understand context
3. **Keep translations updated** - Run `makemessages` after code changes
4. **Test all languages** - Ensure translations look good in UI
5. **Provide context** - Use comments in `.po` files:
   ```po
   #: sellers/views.py:42
   msgid "Dashboard"
   msgstr "Panel"
   ```

---

## Troubleshooting

### Language selector not showing?
- Ensure `django.middleware.locale.LocaleMiddleware` is in `MIDDLEWARE`
- Check that `i18n_patterns()` wraps your URL patterns

### Translations not displaying?
- Run `python manage.py compilemessages`
- Restart the development server
- Clear browser cache and cookies

### "makemessages" command not found?
```bash
# Make sure you're in the right directory
cd /home/ivo/projects/vintage_shop

# Activate virtual environment
source venv/bin/activate

# Run the command
python manage.py makemessages -a
```

---

## Next Steps

1. Mark strings in templates and Python files using `_()` and `{% trans %}`
2. Run `python manage.py makemessages -a` to extract strings
3. Edit `.po` files in `locale/LANGUAGE/LC_MESSAGES/` with translations
4. Run `python manage.py compilemessages` to compile
5. Test language switcher in the UI
6. Deploy and monitor

---

## Resources

- [Django i18n Documentation](https://docs.djangoproject.com/en/stable/topics/i18n/)
- [gettext Format](https://www.gnu.org/software/gettext/manual/gettext.html)
- [Translating Django Applications](https://docs.djangoproject.com/en/stable/topics/i18n/translation/)
