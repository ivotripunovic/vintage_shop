"""
Production settings must know the site is served over HTTPS behind nginx.

The test settings run with DEBUG=True, so the production block in
config/settings.py is loaded in a subprocess with DEBUG=False, the way
gunicorn loads it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PRINT_SETTINGS = """
import json
import config.settings as s
print(json.dumps({
    "proxy_header": list(getattr(s, "SECURE_PROXY_SSL_HEADER", None) or []),
    "session_secure": getattr(s, "SESSION_COOKIE_SECURE", False),
    "csrf_secure": getattr(s, "CSRF_COOKIE_SECURE", False),
    "hsts": getattr(s, "SECURE_HSTS_SECONDS", 0),
    "allauth_protocol": getattr(s, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http"),
    "client_ip_header": getattr(s, "ALLAUTH_TRUSTED_CLIENT_IP_HEADER", None),
}))
"""


def load_settings(**env):
    result = subprocess.run(
        [sys.executable, "-c", PRINT_SETTINGS],
        cwd=ROOT,
        # Pin the vars under test so a developer's .env or shell cannot change
        # them (decouple prefers os.environ over .env)
        env={
            **os.environ,
            "SECRET_KEY": "x" * 50,
            "SECURE_HSTS_SECONDS": "0",
            **env,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_production_trusts_nginx_https_header_and_secures_cookies():
    s = load_settings(DEBUG="False")
    assert s["proxy_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert s["session_secure"] is True
    assert s["csrf_secure"] is True
    assert s["hsts"] == 0
    assert s["allauth_protocol"] == "https"
    assert s["client_ip_header"] == "X-Real-IP"


@pytest.mark.slow
def test_hsts_is_opt_in_from_env():
    assert load_settings(DEBUG="False", SECURE_HSTS_SECONDS="3600")["hsts"] == 3600


@pytest.mark.slow
def test_development_keeps_plain_http():
    s = load_settings(DEBUG="True")
    assert s["proxy_header"] == []
    assert s["session_secure"] is False
    assert s["csrf_secure"] is False
    assert s["allauth_protocol"] == "http"


def test_site_domain_check_warns_without_https():
    from django.test import override_settings

    from core.checks import site_domain_uses_https

    with override_settings(DEBUG=False, SITE_DOMAIN="http://www.example.com"):
        assert [w.id for w in site_domain_uses_https(None)] == ["core.W001"]
    with override_settings(DEBUG=False, SITE_DOMAIN="https://www.example.com"):
        assert site_domain_uses_https(None) == []
    with override_settings(DEBUG=True, SITE_DOMAIN="http://localhost:8000"):
        assert site_domain_uses_https(None) == []


@pytest.mark.django_db
@pytest.mark.parametrize("secure", [True, False])
def test_preview_bypass_cookie_follows_secure_cookie_setting(client, secure):
    """The bypass cookie's value is the preview secret; keep it off plain HTTP."""
    from django.test import override_settings

    from core.test_waitlist import _middleware_with_coming_soon_gate

    with override_settings(
        COMING_SOON=True,
        COMING_SOON_SECRET="s3cret",
        SESSION_COOKIE_SECURE=secure,
        MIDDLEWARE=_middleware_with_coming_soon_gate(),
    ):
        response = client.get("/?preview=s3cret")
    cookie = response.cookies["vs_preview"]
    assert bool(cookie["secure"]) is secure
    assert cookie["httponly"]
