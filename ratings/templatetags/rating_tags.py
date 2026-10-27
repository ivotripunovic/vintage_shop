from django import template

register = template.Library()


@register.filter
def stars(score):
    """Render a 1–5 score (possibly an average) as five stars, rounded."""
    if score is None:
        return ""
    filled = max(0, min(5, round(score)))
    return "★" * filled + "☆" * (5 - filled)
