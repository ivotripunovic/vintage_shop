"""
Every user-facing HTML page must carry the site styling.

Pages, including django-allauth's and the 403/404/CSRF error pages, render
inside the site layout (base.html). The exceptions use the standalone shell
errors/_standalone.html on purpose: 400 and 500 (rendered without a usable
request), and every error page shown to a visitor held by the Coming Soon gate,
so the unreleased site's navigation is never shown.
"""

import pytest
from django.template import loader
from django.test import override_settings

from core.test_waitlist import _middleware_with_coming_soon_gate
from users.models import User

SITE_CSS = "cdn.tailwindcss.com"
ALLAUTH_BARE_MENU = "Menu:"

ALLAUTH_PAGES = [
    "/auth/confirm-email/",
    "/auth/confirm-email/invalid-key/",
    "/auth/inactive/",
    "/auth/login/",
    "/auth/signup/",
    "/auth/password/reset/",
    "/auth/password/reset/done/",
    "/auth/password/reset/key/1-invalid/",
    "/auth/password/reset/key/done/",
    "/auth/social/login/cancelled/",
]


# allauth's own (English) page text; our templates/account/* replace it
ENGLISH = [
    "Sign In",
    "Sign Up",
    "Sign Out",
    "Password Reset",
    "Verify Your Email",
    "Confirm Email Address",
    "Change Password",
    "Email Address",
    "Account Inactive",
    "Login Cancelled",
    "Third-Party Login Failure",
    "Forgot your password",
]


def assert_styled(response):
    body = response.content.decode()
    assert SITE_CSS in body
    assert ALLAUTH_BARE_MENU not in body


def assert_serbian(response):
    body = response.content.decode()
    found = [phrase for phrase in ENGLISH if phrase in body]
    assert not found, f"English allauth text on {response.request['PATH_INFO']}"


@pytest.mark.django_db
@pytest.mark.parametrize("path", ALLAUTH_PAGES)
def test_allauth_pages_use_site_layout(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert_styled(response)
    assert_serbian(response)


@pytest.mark.django_db
def test_allauth_logged_in_pages_use_site_layout(client):
    user = User.objects.create_user(
        email="styled@example.com",
        username="styled@example.com",
        password="pw-12345678",
    )
    user.mark_email_verified()
    client.force_login(user)
    for path in (
        "/auth/email/",
        "/auth/logout/",
        "/auth/password/change/",
        "/auth/reauthenticate/",
        "/auth/social/",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert_styled(response)
        assert_serbian(response)


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_404_page_uses_site_layout(client):
    response = client.get("/this-page-does-not-exist/")
    assert response.status_code == 404
    assert_styled(response)


@pytest.mark.django_db
def test_permission_denied_uses_site_layout(client):
    """A buyer opening a seller-only page gets the styled 403 page."""
    buyer = User.objects.create_user(
        email="buyer@example.com",
        username="buyer@example.com",
        password="pw-12345678",
        is_buyer=True,
    )
    buyer.mark_email_verified()
    client.force_login(buyer)
    response = client.get("/products/1/edit/")
    assert response.status_code == 403
    assert_styled(response)


def test_500_template_is_styled_without_context():
    html = loader.get_template("500.html").render()
    assert SITE_CSS in html


SITE_NAV = 'id="nav-categories"'
SITE_HEADER = "<header"


@pytest.mark.django_db
@override_settings(DEBUG=False, ALLOWED_HOSTS=["good.example"])
def test_disallowed_host_returns_styled_400(client):
    """Raised before AuthenticationMiddleware, so request.user does not exist."""
    response = client.get("/", HTTP_HOST="evil.example")
    assert response.status_code == 400
    assert SITE_CSS in response.content.decode()


@pytest.mark.django_db
def test_csrf_failure_uses_site_layout():
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    response = client.post("/auth/login/", {"email": "x@example.com"})
    assert response.status_code == 403
    assert_styled(response)


@pytest.mark.django_db
@override_settings(
    DEBUG=False, COMING_SOON=True, MIDDLEWARE=_middleware_with_coming_soon_gate()
)
def test_error_pages_hide_site_nav_while_coming_soon(client):
    """The gate lets /waitlist/ through; its 404 must not reveal the site menu."""
    response = client.get("/waitlist/no-such-page/")
    assert response.status_code == 404
    body = response.content.decode()
    assert SITE_CSS in body
    assert SITE_NAV not in body
    assert SITE_HEADER not in body


@pytest.mark.django_db
@override_settings(
    DEBUG=False, COMING_SOON=True, MIDDLEWARE=_middleware_with_coming_soon_gate()
)
def test_staff_keep_site_nav_on_error_pages_while_coming_soon(client):
    """Staff browse the gated site, so their error pages keep the layout."""
    staff = User.objects.create_user(
        email="staff@example.com",
        username="staff@example.com",
        password="pw-12345678",
        is_staff=True,
    )
    staff.mark_email_verified()
    client.force_login(staff)
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert SITE_NAV in response.content.decode()


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    COMING_SOON=True,
    COMING_SOON_SECRET="s3cret",
    MIDDLEWARE=_middleware_with_coming_soon_gate(),
)
def test_preview_visitors_keep_site_nav_on_error_pages(client):
    client.cookies["vs_preview"] = "s3cret"
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert SITE_NAV in response.content.decode()


@override_settings(COMING_SOON=True)
def test_error_template_without_request_uses_standalone_shell():
    html = loader.get_template("404.html").render()
    assert SITE_CSS in html
    assert SITE_HEADER not in html


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_error_pages_show_site_nav_normally(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert SITE_NAV in response.content.decode()
