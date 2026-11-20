from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def site_domain_uses_https(app_configs, **kwargs):
    """SITE_DOMAIN builds the links in verification, reset and chat emails."""
    if settings.DEBUG or settings.SITE_DOMAIN.startswith("https://"):
        return []
    return [
        Warning(
            f"SITE_DOMAIN is {settings.SITE_DOMAIN!r}; emailed links will not use "
            "HTTPS.",
            hint="Set SITE_DOMAIN=https://www.<domain> in the server .env.",
            id="core.W001",
        )
    ]
