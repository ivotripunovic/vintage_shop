from django.test import TestCase, override_settings
from django.urls import reverse


class RobotsTests(TestCase):
    def test_served_as_text_plain(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

    @override_settings(COMING_SOON=True)
    def test_deindexed_while_gated(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(response.content, b"User-agent: *\nDisallow: /\n")

    @override_settings(COMING_SOON=False)
    def test_unlocked_after_launch(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(
            response.content,
            b"User-agent: *\n"
            b"Disallow: /admin/\n"
            b"Disallow: /auth/\n"
            b"Disallow: /chat/\n"
            b"Disallow: /waitlist/\n"
            b"Allow: /\n",
        )

    def test_served_without_language_prefix(self):
        self.assertEqual(reverse("robots"), "/robots.txt")

    @override_settings(COMING_SOON=True)
    def test_passes_coming_soon_gate(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(response["Content-Type"], "text/plain")
