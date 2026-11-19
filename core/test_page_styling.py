"""
Every user-facing HTML page must render inside the site layout (base.html),
including pages served by django-allauth and Django's error handlers.
"""

import pytest
from django.template import loader
from django.test import override_settings

from users.models import User

SITE_CSS = "cdn.tailwindcss.com"
ALLAUTH_BARE_MENU = "Menu:"

ALLAUTH_PAGES = [
    "/auth/accounts/confirm-email/",
    "/auth/accounts/confirm-email/invalid-key/",
    "/auth/accounts/inactive/",
    "/auth/accounts/login/",
    "/auth/accounts/signup/",
    "/auth/accounts/password/reset/",
    "/auth/accounts/password/reset/done/",
    "/auth/accounts/password/reset/key/1-invalid/",
    "/auth/accounts/password/reset/key/done/",
    "/auth/social/login/cancelled/",
]


def assert_styled(response):
    body = response.content.decode()
    assert SITE_CSS in body
    assert ALLAUTH_BARE_MENU not in body


@pytest.mark.django_db
@pytest.mark.parametrize("path", ALLAUTH_PAGES)
def test_allauth_pages_use_site_layout(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert_styled(response)


@pytest.mark.django_db
def test_allauth_logged_in_pages_use_site_layout(client):
    user = User.objects.create_user(
        email="styled@example.com",
        username="styled@example.com",
        password="pw-12345678",
        email_verified=True,
    )
    client.force_login(user)
    for path in ("/auth/accounts/email/", "/auth/accounts/logout/"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert_styled(response)


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
        email_verified=True,
    )
    client.force_login(buyer)
    response = client.get("/products/1/edit/")
    assert response.status_code == 403
    assert_styled(response)


def test_500_template_is_styled_without_context():
    html = loader.get_template("500.html").render()
    assert SITE_CSS in html
