import datetime
import time
from io import StringIO
from unittest import mock

import dns.exception
import dns.resolver
from django.conf import settings as django_settings
from django.core import mail, signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import email_checks
from core.emails import (
    CONFIRM_MAX_AGE_SECONDS,
    make_confirm_token,
    make_unsubscribe_token,
)
from core.forms import TIMESTAMP_SALT, WaitlistSubscribeForm
from core.models import WaitlistSubscriber
from core.views import ATTEMPT_LIMIT_MAX_PER_IP


def valid_post_data(email="visitor@example.com", ip_age_seconds=10):
    """POST payload for a human-like waitlist submission."""
    rendered_at = time.time() - ip_age_seconds
    return {
        "email": email,
        "website": "",
        "timestamp": signing.dumps(rendered_at, salt=TIMESTAMP_SALT),
    }


class WaitlistSubscribeFormTests(TestCase):
    def test_honeypot_filled_is_flagged_as_bot(self):
        data = valid_post_data()
        data["website"] = "http://spam.example.com"
        form = WaitlistSubscribeForm(data)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.is_bot())

    def test_too_fast_submission_is_flagged_as_bot(self):
        data = valid_post_data(ip_age_seconds=0)
        form = WaitlistSubscribeForm(data)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.is_bot())

    def test_missing_timestamp_is_flagged_as_bot(self):
        form = WaitlistSubscribeForm({"email": "visitor@example.com", "website": ""})
        self.assertTrue(form.is_valid())
        self.assertTrue(form.is_bot())

    def test_human_like_submission_is_not_flagged(self):
        form = WaitlistSubscribeForm(valid_post_data())
        self.assertTrue(form.is_valid())
        self.assertFalse(form.is_bot())

    def test_invalid_email_fails_validation(self):
        data = valid_post_data(email="not-an-email")
        form = WaitlistSubscribeForm(data)
        self.assertFalse(form.is_valid())


@override_settings(COMING_SOON=False)
class WaitlistSubscribeViewTests(TestCase):
    """COMING_SOON is disabled here since the view is reached directly by URL."""

    def setUp(self):
        cache.clear()

    def test_valid_submission_creates_subscriber(self):
        response = self.client.post(
            reverse("waitlist_subscribe"), valid_post_data("new@example.com")
        )
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(
            WaitlistSubscriber.objects.filter(email="new@example.com").exists()
        )

    def test_email_is_normalized(self):
        self.client.post(
            reverse("waitlist_subscribe"), valid_post_data("  Mixed@Example.com  ")
        )
        self.assertTrue(
            WaitlistSubscriber.objects.filter(email="mixed@example.com").exists()
        )

    def test_duplicate_email_is_not_duplicated(self):
        WaitlistSubscriber.objects.create(email="dup@example.com")
        self.client.post(
            reverse("waitlist_subscribe"), valid_post_data("dup@example.com")
        )
        self.assertEqual(
            WaitlistSubscriber.objects.filter(email="dup@example.com").count(), 1
        )

    def test_honeypot_submission_is_not_saved(self):
        data = valid_post_data("bot@example.com")
        data["website"] = "http://spam.example.com"
        self.client.post(reverse("waitlist_subscribe"), data)
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="bot@example.com").exists()
        )

    def test_too_fast_submission_is_not_saved(self):
        data = valid_post_data("fast@example.com", ip_age_seconds=0)
        self.client.post(reverse("waitlist_subscribe"), data)
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="fast@example.com").exists()
        )

    def test_invalid_email_is_not_saved(self):
        self.client.post(reverse("waitlist_subscribe"), valid_post_data("not-an-email"))
        self.assertEqual(WaitlistSubscriber.objects.count(), 0)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("waitlist_subscribe"))
        self.assertEqual(response.status_code, 405)

    def test_rate_limit_per_ip(self):
        for i in range(5):
            WaitlistSubscriber.objects.create(
                email=f"existing{i}@example.com",
                ip_address="127.0.0.1",
                created_at=timezone.now(),
            )
        self.client.post(
            reverse("waitlist_subscribe"), valid_post_data("blocked@example.com")
        )
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="blocked@example.com").exists()
        )


def _middleware_with_coming_soon_gate():
    """
    Test settings strip ComingSoonMiddleware out of MIDDLEWARE so other view
    tests aren't gated. Re-add it for tests that specifically exercise the gate.
    """
    middleware = list(django_settings.MIDDLEWARE)
    index = middleware.index("django.contrib.messages.middleware.MessageMiddleware")
    middleware.insert(index + 1, "core.middleware.ComingSoonMiddleware")
    return middleware


@override_settings(
    COMING_SOON=True,
    COMING_SOON_SECRET="",
    MIDDLEWARE=_middleware_with_coming_soon_gate(),
)
class ComingSoonWaitlistIntegrationTests(TestCase):
    """Exercises the waitlist form as an anonymous visitor sees it, gate and all."""

    def setUp(self):
        cache.clear()

    def test_coming_soon_page_renders_waitlist_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "waitlist/subscribe")

    def test_subscribe_bypasses_gate_and_redirect_shows_message(self):
        get_response = self.client.get("/")
        self.assertContains(get_response, 'name="timestamp"')

        response = self.client.post(
            reverse("waitlist_subscribe"),
            valid_post_data("gated@example.com"),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WaitlistSubscriber.objects.filter(email="gated@example.com").exists()
        )

        messages = list(response.context["messages"])
        self.assertTrue(any("Hvala" in str(m) for m in messages))
        self.assertContains(response, "Hvala")

    def test_confirm_and_unsubscribe_links_bypass_gate(self):
        WaitlistSubscriber.objects.create(email="gate@example.com")

        response = self.client.get(
            reverse("waitlist_confirm", args=[make_confirm_token("gate@example.com")])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WaitlistSubscriber.objects.get(email="gate@example.com").is_confirmed
        )

        response = self.client.get(
            reverse(
                "waitlist_unsubscribe",
                args=[make_unsubscribe_token("gate@example.com")],
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="gate@example.com").exists()
        )


class EmailChecksTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_typo_domains_get_a_suggestion(self):
        self.assertEqual(email_checks.suggest_domain("gmial.com"), "gmail.com")
        self.assertEqual(email_checks.suggest_domain("gmail.con"), "gmail.com")
        self.assertEqual(email_checks.suggest_domain("mts.sr"), "mts.rs")

    def test_real_domains_are_not_flagged_as_typos(self):
        for domain in [
            "gmail.com",
            "yahoo.co.uk",
            "yahoo.de",
            "ymail.com",
            "mail.com",
            "firma.rs",
        ]:
            self.assertIsNone(email_checks.suggest_domain(domain), domain)

    def test_typo_is_rejected_with_suggestion(self):
        with self.assertRaisesMessage(ValidationError, "ana@gmail.com"):
            email_checks.validate_waitlist_email("ana@gmial.com")

    def test_disposable_domain_and_subdomain_are_rejected(self):
        for email in ["a@mailinator.com", "a@inbox.mailinator.com"]:
            with self.assertRaises(ValidationError):
                email_checks.validate_waitlist_email(email)

    @override_settings(WAITLIST_CHECK_DNS=True)
    @mock.patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN)
    def test_nonexistent_domain_is_rejected(self, _resolve):
        with self.assertRaisesMessage(ValidationError, "ne postoji"):
            email_checks.validate_waitlist_email("a@no-such-domain-xyz.com")

    @override_settings(WAITLIST_CHECK_DNS=True)
    @mock.patch("dns.resolver.Resolver.resolve", side_effect=dns.exception.Timeout)
    def test_dns_timeout_accepts_and_is_not_cached(self, resolve):
        email_checks.validate_waitlist_email("a@slow-dns.com")
        email_checks.validate_waitlist_email("a@slow-dns.com")
        self.assertEqual(resolve.call_count, 2)

    @override_settings(WAITLIST_CHECK_DNS=True)
    @mock.patch("dns.resolver.Resolver.resolve")
    def test_dns_result_is_cached_per_domain(self, resolve):
        resolve.return_value = [mock.Mock(exchange="mx.firma.rs.")]
        email_checks.validate_waitlist_email("a@firma.rs")
        email_checks.validate_waitlist_email("b@firma.rs")
        self.assertEqual(resolve.call_count, 1)

    @override_settings(WAITLIST_CHECK_DNS=True)
    @mock.patch("dns.resolver.Resolver.resolve")
    def test_null_mx_is_rejected(self, resolve):
        resolve.return_value = [mock.Mock(exchange=".")]
        with self.assertRaises(ValidationError):
            email_checks.validate_waitlist_email("a@nomail.com")

    @override_settings(WAITLIST_CHECK_DNS=True)
    @mock.patch("dns.resolver.Resolver.resolve")
    def test_no_mx_falls_back_to_a_record(self, resolve):
        resolve.side_effect = [dns.resolver.NoAnswer, [mock.Mock()]]
        email_checks.validate_waitlist_email("a@a-record-only.com")


@override_settings(COMING_SOON=False)
class WaitlistConfirmationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_subscribe_sends_one_confirmation_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("waitlist_subscribe"), valid_post_data("new@example.com")
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertIn("/waitlist/confirm/", mail.outbox[0].body)
        self.assertFalse(
            WaitlistSubscriber.objects.get(email="new@example.com").is_confirmed
        )

    def test_rejected_email_shows_specific_error(self):
        response = self.client.post(
            reverse("waitlist_subscribe"),
            valid_post_data("a@mailinator.com"),
            follow=True,
        )
        self.assertContains(response, "Privremene email adrese")
        self.assertEqual(WaitlistSubscriber.objects.count(), 0)

    def test_confirm_link_marks_subscriber_confirmed(self):
        WaitlistSubscriber.objects.create(email="c@example.com")
        self.client.get(
            reverse("waitlist_confirm", args=[make_confirm_token("c@example.com")])
        )
        self.assertTrue(
            WaitlistSubscriber.objects.get(email="c@example.com").is_confirmed
        )

    def test_tampered_token_is_rejected(self):
        WaitlistSubscriber.objects.create(email="c@example.com")
        token = make_confirm_token("c@example.com") + "x"
        self.client.get(reverse("waitlist_confirm", args=[token]))
        self.assertFalse(
            WaitlistSubscriber.objects.get(email="c@example.com").is_confirmed
        )

    def test_expired_token_is_rejected(self):
        WaitlistSubscriber.objects.create(email="c@example.com")
        token = make_confirm_token("c@example.com")
        later = time.time() + CONFIRM_MAX_AGE_SECONDS + 60
        with mock.patch("django.core.signing.time.time", return_value=later):
            self.client.get(reverse("waitlist_confirm", args=[token]))
        self.assertFalse(
            WaitlistSubscriber.objects.get(email="c@example.com").is_confirmed
        )

    def test_resend_respects_cooldown(self):
        WaitlistSubscriber.objects.create(
            email="r@example.com", confirmation_sent_at=timezone.now()
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("waitlist_subscribe"), valid_post_data("r@example.com")
            )
        self.assertEqual(len(mail.outbox), 0)

        WaitlistSubscriber.objects.filter(email="r@example.com").update(
            confirmation_sent_at=timezone.now() - datetime.timedelta(minutes=11)
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("waitlist_subscribe"), valid_post_data("r@example.com")
            )
        self.assertEqual(len(mail.outbox), 1)

    def test_confirmed_subscriber_gets_no_new_email(self):
        WaitlistSubscriber.objects.create(
            email="done@example.com", confirmed_at=timezone.now()
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("waitlist_subscribe"), valid_post_data("done@example.com")
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_unsubscribe_deletes_subscriber(self):
        WaitlistSubscriber.objects.create(
            email="u@example.com", confirmed_at=timezone.now()
        )
        self.client.get(
            reverse(
                "waitlist_unsubscribe", args=[make_unsubscribe_token("u@example.com")]
            )
        )
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="u@example.com").exists()
        )

    def test_confirm_token_cannot_be_used_to_unsubscribe(self):
        WaitlistSubscriber.objects.create(email="u@example.com")
        self.client.get(
            reverse("waitlist_unsubscribe", args=[make_confirm_token("u@example.com")])
        )
        self.assertTrue(
            WaitlistSubscriber.objects.filter(email="u@example.com").exists()
        )


@override_settings(COMING_SOON=False)
class WaitlistAbuseTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_spoofed_forwarded_for_does_not_bypass_ip_limit(self):
        for i in range(5):
            WaitlistSubscriber.objects.create(
                email=f"existing{i}@example.com", ip_address="127.0.0.1"
            )
        self.client.post(
            reverse("waitlist_subscribe"),
            valid_post_data("spoof@example.com"),
            HTTP_X_FORWARDED_FOR="203.0.113.9",
        )
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="spoof@example.com").exists()
        )

    def test_real_ip_header_from_nginx_is_used(self):
        self.client.post(
            reverse("waitlist_subscribe"),
            valid_post_data("ip@example.com"),
            HTTP_X_REAL_IP="198.51.100.7",
        )
        self.assertEqual(
            WaitlistSubscriber.objects.get(email="ip@example.com").ip_address,
            "198.51.100.7",
        )

    def test_attempt_limit_counts_every_post(self):
        for _ in range(ATTEMPT_LIMIT_MAX_PER_IP):
            self.client.post(
                reverse("waitlist_subscribe"), valid_post_data("not-an-email")
            )
        self.client.post(
            reverse("waitlist_subscribe"), valid_post_data("late@example.com")
        )
        self.assertFalse(
            WaitlistSubscriber.objects.filter(email="late@example.com").exists()
        )


class SendLaunchEmailCommandTests(TestCase):
    def setUp(self):
        WaitlistSubscriber.objects.create(
            email="yes@example.com", confirmed_at=timezone.now()
        )
        WaitlistSubscriber.objects.create(email="unconfirmed@example.com")
        WaitlistSubscriber.objects.create(
            email="already@example.com",
            confirmed_at=timezone.now(),
            notified_at=timezone.now(),
        )

    def test_sends_only_to_confirmed_not_notified(self):
        call_command("send_launch_email", stdout=StringIO())
        self.assertEqual([m.to for m in mail.outbox], [["yes@example.com"]])
        self.assertIn("/waitlist/unsubscribe/", mail.outbox[0].body)
        self.assertIn("List-Unsubscribe", mail.outbox[0].extra_headers)
        self.assertIsNotNone(
            WaitlistSubscriber.objects.get(email="yes@example.com").notified_at
        )

    def test_rerun_sends_nothing(self):
        call_command("send_launch_email", stdout=StringIO())
        call_command("send_launch_email", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_dry_run_sends_nothing(self):
        out = StringIO()
        call_command("send_launch_email", "--dry-run", stdout=out)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("yes@example.com", out.getvalue())
        self.assertIsNone(
            WaitlistSubscriber.objects.get(email="yes@example.com").notified_at
        )
