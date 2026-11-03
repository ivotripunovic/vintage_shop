from django.conf import settings
from django.shortcuts import render

from .forms import WaitlistSubscribeForm

BYPASS_COOKIE = "vs_preview"
WAITLIST_PREFIX = "/waitlist/"
HEALTH_PATH = "/health/"
MANIFEST_PATH = "/manifest.webmanifest"
ROBOTS_PATH = "/robots.txt"


class ComingSoonMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "COMING_SOON", False):
            return self.get_response(request)

        # Admin, static/media assets, the favicon, the web app manifest, and
        # the uptime monitor's health check always pass through
        if request.path.startswith(
            ("/admin/", "/static/", "/media/")
        ) or request.path in (
            HEALTH_PATH,
            "/favicon.ico",
            MANIFEST_PATH,
            ROBOTS_PATH,
        ):
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


class HeadResponseMiddleware:
    """
    Send HEAD responses without a body, as RFC 9110 requires.

    Django leaves this to the server under WSGI; gunicorn 26 drops the body
    but logs a warning each time (UptimeRobot's HEAD /health/ every 5
    minutes). Content-Length keeps the GET's value, as HEAD should report.
    Outermost in MIDDLEWARE, so it sees the final response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method != "HEAD":
            return response
        status = response.status_code
        if status < 200 or status in (204, 304):
            # No body to begin with, and Content-Length: 0 would be wrong on
            # a 304 (it must match the full 200 response)
            return response
        if response.streaming:
            # Not read; a file behind it is still closed when the server
            # closes the response
            response.streaming_content = []
        else:
            # Keep a length set earlier (CommonMiddleware, or a view that
            # answers HEAD itself); count it only when missing
            response.headers.setdefault("Content-Length", str(len(response.content)))
            response.content = b""
        return response
