from django import template

register = template.Library()


@register.filter
def rsd(value):
    """Format a price as Serbian dinars: 1.234 RSD (rounded, period as thousands separator)."""
    try:
        amount = round(float(value))
        formatted = f"{amount:,}".replace(",", ".")
        return f"{formatted} RSD"
    except (ValueError, TypeError):
        return value
