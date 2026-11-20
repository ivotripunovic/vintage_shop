"""
Email auth through allauth (#77): signup, verification, login, logout,
password reset and change, email change, and the redirects from the old
custom-flow URLs.
"""

import re

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from users.models import User

PASSWORD = "Pw-strong-123"


def make_user(email="a@example.com", verified=True, **extra):
    user = User.objects.create_user(
        email=email, username=email, password=PASSWORD, **extra
    )
    if verified:
        user.email_verified = True
        user.save()
    return user


def link_in(message, path_prefix):
    match = re.search(rf"https?://[^\s]+({re.escape(path_prefix)}[^\s]*)", message.body)
    assert match, message.body
    return match.group(1)


def signup(client, email="new@example.com", **extra):
    return client.post(
        reverse("account_signup"),
        {"email": email, "password1": PASSWORD, "password2": PASSWORD, **extra},
    )


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    cache.clear()


@pytest.mark.django_db
class TestSignupAndVerification:
    def test_signup_sends_serbian_confirmation_and_sets_no_roles(self, client):
        response = signup(client, first_name="Ana")
        assert response.status_code == 302
        assert response["Location"] == reverse("account_email_verification_sent")
        user = User.objects.get(email="new@example.com")
        assert not user.is_seller
        assert not user.email_verified
        assert user.first_name == "Ana"
        assert not hasattr(user, "seller_profile")
        [message] = mail.outbox
        assert message.to == ["new@example.com"]
        assert message.subject.startswith("Potvrdite vašu")
        assert settings.SITE_NAME in message.subject
        assert "Dobrodošli" in message.body
        assert "example.com]" not in message.subject  # no allauth prefix

    def test_confirming_verifies_both_records_and_logs_in(self, client):
        signup(client)
        confirm_path = link_in(mail.outbox[0], "/auth/confirm-email/")
        page = client.get(confirm_path)
        assert "Potvrdi" in page.content.decode()
        response = client.post(confirm_path)
        assert response.status_code == 302
        assert response["Location"] == reverse("social-signup-complete")
        user = User.objects.get(email="new@example.com")
        assert user.email_verified
        assert EmailAddress.objects.get(user=user).verified
        assert client.get(reverse("account-settings")).status_code == 200

    def test_duplicate_signup_does_not_reveal_the_account(self, client):
        make_user("taken@example.com")
        response = signup(client, email="taken@example.com")
        # Same page as a new signup; the owner gets a "you already have an
        # account" email instead (ACCOUNT_PREVENT_ENUMERATION)
        assert response["Location"] == reverse("account_email_verification_sent")
        assert User.objects.filter(email="taken@example.com").count() == 1
        [message] = mail.outbox
        assert "već postoji" in message.subject

    def test_password_mismatch_error_is_serbian(self, client):
        response = client.post(
            reverse("account_signup"),
            {"email": "x@example.com", "password1": PASSWORD, "password2": "other"},
        )
        assert "Lozinke se ne poklapaju." in response.content.decode()

    def test_weak_password_error_is_serbian(self, client):
        response = client.post(
            reverse("account_signup"),
            {"email": "x@example.com", "password1": "123", "password2": "123"},
        )
        body = response.content.decode()
        assert "Lozinka je prekratka" in body
        assert "too short" not in body


@pytest.mark.django_db
class TestLogin:
    def login(self, client, email="a@example.com", password=PASSWORD, next_url=None):
        url = reverse("account_login")
        if next_url:
            url += f"?next={next_url}"
        return client.post(url, {"login": email, "password": password})

    def test_verified_user_logs_in_and_follows_next(self, client):
        make_user()
        response = self.login(client, next_url="/products/")
        assert response["Location"] == "/products/"

    def test_external_next_is_ignored(self, client):
        make_user()
        response = self.login(client, next_url="https://evil.example/")
        assert response["Location"] == "/"

    def test_unverified_user_gets_a_new_link_instead_of_logging_in(self, client):
        make_user(verified=False)
        response = self.login(client)
        assert response["Location"] == reverse("account_email_verification_sent")
        assert len(mail.outbox) == 1
        assert client.get(reverse("account-settings")).status_code == 302

    def test_next_survives_email_verification(self, client):
        """Deferred from #82: unverified users used to lose their target."""
        make_user(verified=False)
        self.login(client, next_url="/products/")
        confirm_path = link_in(mail.outbox[0], "/auth/confirm-email/")
        response = client.post(confirm_path)
        assert response["Location"] == "/products/"

    def test_wrong_password_error_is_serbian(self, client):
        make_user()
        response = self.login(client, password="wrong")
        assert "Email adresa ili lozinka nisu ispravni." in response.content.decode()

    def test_repeated_failures_are_rate_limited(self, client):
        make_user()
        for _ in range(5):
            self.login(client, password="wrong")
        response = self.login(client)  # right password, but locked out
        assert "Previše neuspelih pokušaja" in response.content.decode()
        assert client.get(reverse("account-settings")).status_code == 302

    def test_logout_needs_post(self, client):
        client.force_login(make_user())
        page = client.get(reverse("account_logout"))
        assert "Da li želite da se odjavite?" in page.content.decode()
        assert client.get(reverse("account-settings")).status_code == 200
        client.post(reverse("account_logout"))
        assert client.get(reverse("account-settings")).status_code == 302


@pytest.mark.django_db
class TestPasswordReset:
    def test_reset_end_to_end(self, client):
        make_user()
        response = client.post(
            reverse("account_reset_password"), {"email": "a@example.com"}
        )
        assert response["Location"] == reverse("account_reset_password_done")
        [message] = mail.outbox
        assert message.subject.startswith("Resetovanje lozinke")
        reset_path = link_in(message, "/auth/password/reset/key/")
        form_page = client.get(reset_path, follow=True)
        action = (
            form_page.redirect_chain[-1][0] if form_page.redirect_chain else reset_path
        )
        new = "Nova-lozinka-456"
        response = client.post(action, {"password1": new, "password2": new})
        assert response["Location"] == reverse("account_reset_password_from_key_done")
        client.logout()
        response = client.post(
            reverse("account_login"), {"login": "a@example.com", "password": new}
        )
        assert response["Location"] == "/"
        # The link is single-use
        assert "Link nije važeći" in client.get(action).content.decode()

    def test_unknown_email_looks_the_same_and_reveals_nothing(self, client):
        response = client.post(
            reverse("account_reset_password"), {"email": "nobody@example.com"}
        )
        assert response["Location"] == reverse("account_reset_password_done")
        [message] = mail.outbox
        assert message.to == ["nobody@example.com"]
        assert "ne postoji" in message.body

    def test_invalid_key_page_is_serbian(self, client):
        response = client.get("/auth/password/reset/key/1-bad/")
        assert "Link nije važeći" in response.content.decode()


@pytest.mark.django_db
class TestPasswordChange:
    def test_change_requires_current_password(self, client):
        client.force_login(make_user())
        response = client.post(
            reverse("account_change_password"),
            {
                "oldpassword": "wrong",
                "password1": "Nova-123-x",
                "password2": "Nova-123-x",
            },
        )
        assert "Unesite vašu trenutnu lozinku." in response.content.decode()

    def test_social_user_without_password_is_sent_to_set_password(self, client):
        user = make_user()
        user.set_unusable_password()
        user.save()
        client.force_login(user)
        response = client.get(reverse("account_change_password"))
        assert response["Location"] == reverse("account_set_password")


@pytest.mark.django_db
class TestEmailChange:
    def test_change_needs_confirmation_of_the_new_address(self, client):
        user = make_user("old@example.com")
        client.force_login(user)
        client.post(
            reverse("account_email"),
            {"action_add": "", "email": "new@example.com"},
        )
        user.refresh_from_db()
        assert user.email == "old@example.com"  # unchanged until confirmed
        [message] = mail.outbox
        assert message.to == ["new@example.com"]
        confirm_path = link_in(message, "/auth/confirm-email/")
        client.post(confirm_path)
        user.refresh_from_db()
        assert user.email == "new@example.com"
        assert user.email_verified
        assert list(
            EmailAddress.objects.filter(user=user).values_list(
                "email", "primary", "verified"
            )
        ) == [("new@example.com", True, True)]

    def test_page_is_serbian(self, client):
        client.force_login(make_user())
        body = client.get(reverse("account_email")).content.decode()
        assert "Trenutna adresa" in body
        assert "Promeni email" in body


@pytest.mark.django_db
class TestOldUrls:
    @pytest.mark.parametrize(
        "old, new",
        [
            ("/auth/register/", "/auth/signup/"),
            ("/auth/password-reset/", "/auth/password/reset/"),
            ("/auth/reset-password/sometoken/", "/auth/password/reset/"),
            ("/auth/password-change/", "/auth/password/change/"),
            ("/auth/verify-email-resend/", "/auth/email/"),
            ("/auth/accounts/login/", "/auth/login/"),
            ("/auth/accounts/password/reset/", "/auth/password/reset/"),
            ("/auth/login/?next=/products/", "/auth/login/?next=/products/"),
        ],
    )
    def test_redirects(self, client, old, new):
        response = client.get(old)
        if old == new:
            assert response.status_code == 200
        else:
            assert response.status_code == 302
            assert response["Location"] == new

    def test_old_redirects_keep_the_query_string(self, client):
        response = client.get("/auth/register/?next=/products/")
        assert response["Location"] == "/auth/signup/?next=/products/"


@pytest.mark.django_db
class TestStartSelling:
    def test_visitors_sign_up_first(self, client):
        response = client.get(reverse("seller_register"))
        assert response["Location"] == (
            f"{reverse('account_signup')}?next={reverse('social-signup-complete')}"
        )

    def test_signed_in_buyers_go_to_the_welcome_page(self, client):
        client.force_login(make_user())
        response = client.get(reverse("seller_register"))
        assert response["Location"] == reverse("social-signup-complete")

    def test_sellers_go_to_their_dashboard(self, client):
        client.force_login(make_user(is_seller=True))
        response = client.get(reverse("seller_register"))
        assert response["Location"] == reverse("seller_dashboard")

    def test_seller_settings_link_to_the_email_change_page(self, client):
        client.force_login(make_user(is_seller=True))
        body = client.get(reverse("seller_settings")).content.decode()
        assert reverse("account_email") in body
