from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_without(context, *keys):
    """Current query string without the given filters (and the page), for chip links."""
    query = context["request"].GET.copy()
    for key in (*keys, "page"):
        query.pop(key, None)
    return f"?{query.urlencode()}"
