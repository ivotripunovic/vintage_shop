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
}))
"""


def load_settings(**env):
    result = subprocess.run(
        [sys.executable, "-c", PRINT_SETTINGS],
        cwd=ROOT,
        env={**os.environ, "SECRET_KEY": "x" * 50, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_production_trusts_nginx_https_header_and_secures_cookies():
    s = load_settings(DEBUG="False")
    assert s["proxy_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert s["session_secure"] is True
    assert s["csrf_secure"] is True
    assert s["hsts"] == 0
    assert s["allauth_protocol"] == "https"


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
