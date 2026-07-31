import time

from django.conf import settings as django_settings
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.forms import TIMESTAMP_SALT, WaitlistSubscribeForm
from core.models import WaitlistSubscriber


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
