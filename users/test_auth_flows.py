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
        user.mark_email_verified()
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


@pytest.mark.django_db
class TestReviewFixes:
    """Review of #86."""

    def test_email_change_errors_are_serbian(self, client):
        client.force_login(make_user())
        response = client.post(
            reverse("account_email"), {"action_add": "", "email": ""}
        )
        body = response.content.decode()
        assert "Ovo polje je obavezno." in body
        assert "This field is required." not in body
        assert 'placeholder="Email address"' not in body

    def test_reauthenticate_errors_are_serbian(self, client):
        client.force_login(make_user())
        response = client.post(reverse("account_reauthenticate"), {"password": "wrong"})
        body = response.content.decode()
        assert "Incorrect password" not in body
        assert "Pogrešna lozinka." in body

    def test_flash_messages_are_serbian(self, client):
        make_user()
        response = client.post(
            reverse("account_login"),
            {"login": "a@example.com", "password": PASSWORD},
            follow=True,
        )
        body = response.content.decode()
        assert "Prijavljeni ste kao a@example.com." in body
        assert "Successfully signed in" not in body
        response = client.post(reverse("account_logout"), follow=True)
        assert "Odjavili ste se." in response.content.decode()

    def test_rate_limited_page_is_styled_and_serbian(self, client):
        make_user()
        for _ in range(5):
            client.post(reverse("account_reset_password"), {"email": "a@example.com"})
        response = client.post(
            reverse("account_reset_password"), {"email": "a@example.com"}
        )
        assert response.status_code == 429
        body = response.content.decode()
        assert "Previše pokušaja" in body
        assert "Too Many Requests" not in body
        assert "cdn.tailwindcss.com" in body

    def test_behind_nginx_the_client_ip_comes_from_x_real_ip(self, client, settings):
        """Gunicorn on a Unix socket: REMOTE_ADDR is not the visitor's."""
        make_user()
        data = {"login": "a@example.com", "password": PASSWORD}
        without_header = client.post(reverse("account_login"), data, REMOTE_ADDR="")
        assert without_header.status_code == 403  # what production would do

        settings.ALLAUTH_TRUSTED_CLIENT_IP_HEADER = "X-Real-IP"
        response = client.post(
            reverse("account_login"),
            data,
            REMOTE_ADDR="",
            HTTP_X_REAL_IP="203.0.113.7",
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestSocialSignupFromLoginPage:
    """#78, end to end through allauth's complete_social_login."""

    def complete(self, rf, email, verified, process="login"):
        from allauth.core.context import request_context
        from allauth.socialaccount.helpers import complete_social_login
        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sites.models import Site

        app = SocialApp.objects.create(
            provider="google", name="Google", client_id="id", secret="s"
        )
        app.sites.add(Site.objects.get_current())
        request = rf.get("/auth/social/google/login/callback/")
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        request.user = AnonymousUser()
        from allauth.socialaccount.adapter import get_adapter

        provider = get_adapter().get_provider(request, "google")
        sociallogin = SocialLogin(
            provider=provider,
            user=User(email=email),
            account=SocialAccount(provider="google", uid=f"uid-{email}"),
            email_addresses=[
                EmailAddress(email=email, verified=verified, primary=True)
            ],
        )
        sociallogin.state = {"process": process}
        with request_context(request):
            return request, complete_social_login(request, sociallogin)

    def test_new_google_account_signs_up_from_the_login_page(self, rf):
        request, response = self.complete(rf, "new@gmail.com", verified=True)
        user = User.objects.get(email="new@gmail.com")
        assert response.status_code == 302
        assert response["Location"] == reverse("social-signup-complete")
        assert user.email_verified
        assert request.user == user  # logged in
        assert mail.outbox == []  # Google verified it; no extra step

    def test_unverified_or_missing_provider_email_is_sent_to_email_signup(self, rf):
        from allauth.socialaccount.models import SocialAccount, SocialApp

        for email, verified in (("fb@example.com", False), ("", True)):
            SocialApp.objects.all().delete()
            request, response = self.complete(rf, email, verified=verified)
            assert response["Location"] == reverse("account_signup")
            assert not request.user.is_authenticated
            assert not User.objects.exists()
            assert not SocialAccount.objects.exists()
            assert mail.outbox == []

    def test_linked_user_with_unverified_email_still_logs_in(self, rf):
        """#87 review: SOCIALACCOUNT_EMAIL_VERIFICATION stays "none", so a
        linked user whose address is unverified (admin edit) is not blocked."""
        from allauth.socialaccount.models import SocialAccount

        user = make_user("linked@gmail.com", verified=False)
        SocialAccount.objects.create(
            user=user, provider="google", uid="uid-linked@gmail.com"
        )
        request, response = self.complete(rf, "linked@gmail.com", verified=True)
        assert request.user == user
        assert response["Location"] != reverse("account_email_verification_sent")

    def test_another_accounts_pending_row_does_not_block_google_signup(self, rf):
        """#87 third review: allauth counts unverified rows as taken."""
        other = make_user("a@example.com")
        EmailAddress.objects.create(
            user=other, email="new@gmail.com", primary=False, verified=False
        )  # e.g. a pending email change to an address A never proved
        request, response = self.complete(rf, "new@gmail.com", verified=True)
        user = User.objects.get(email="new@gmail.com")
        assert request.user == user
        assert response["Location"] == reverse("social-signup-complete")
        assert not EmailAddress.objects.filter(
            user=other, email="new@gmail.com"
        ).exists()
        assert mail.outbox == []
