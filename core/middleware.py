from django.conf import settings
from django.shortcuts import render

from .forms import WaitlistSubscribeForm

BYPASS_COOKIE = "vs_preview"
WAITLIST_PREFIX = "/waitlist/"
HEALTH_PATH = "/health/"


class ComingSoonMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "COMING_SOON", False):
            return self.get_response(request)

        # Admin, static/media assets, the favicon, and the uptime monitor's
        # health check always pass through
        if request.path.startswith(
            ("/admin/", "/static/", "/media/")
        ) or request.path in (HEALTH_PATH, "/favicon.ico"):
            return self.get_response(request)

        # Waitlist endpoints (subscribe, confirm, unsubscribe) always pass
        # through, so visitors can join the mailing list while the site is gated
        if request.path.startswith(WAITLIST_PREFIX):
            return self.get_response(request)

        # Staff and superusers pass through
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            return self.get_response(request)

        # Secret preview param sets a bypass cookie
        secret = getattr(settings, "COMING_SOON_SECRET", "")
        if secret and request.GET.get("preview") == secret:
            response = self.get_response(request)
            response.set_cookie(
                BYPASS_COOKIE, secret, max_age=60 * 60 * 24 * 7, httponly=True
            )
            return response

        # Bypass cookie grants access
        if secret and request.COOKIES.get(BYPASS_COOKIE) == secret:
            return self.get_response(request)

        return render(
            request,
            "core/coming_soon.html",
            {"waitlist_timestamp": WaitlistSubscribeForm.generate_timestamp()},
            status=200,
        )
