from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def provider_url(context, provider_id, process="login"):
    """Return social provider login URL, or empty string if not configured in DB."""
    try:
        from allauth.socialaccount.adapter import get_adapter

        request = context["request"]
        adapter = get_adapter()
        provider = adapter.get_provider(request, provider_id)
        if not getattr(provider.app, "client_id", None):
            return ""
        return provider.get_login_url(request, process=process)
    except Exception:
        return ""
