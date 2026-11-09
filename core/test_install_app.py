from django.test import TestCase, override_settings
from django.urls import reverse

from core.test_waitlist import _middleware_with_coming_soon_gate


class InstallAppPageTests(TestCase):
    def test_shows_android_and_iphone_steps(self):
        response = self.client.get(reverse("install_app"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/install_app.html")
        self.assertContains(response, "Android (Chrome)")
        self.assertContains(response, "iPhone i iPad (Safari)")

    def test_linked_from_footer(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'href="{reverse("install_app")}"')

    @override_settings(
        COMING_SOON=True,
        COMING_SOON_SECRET="",
        MIDDLEWARE=_middleware_with_coming_soon_gate(),
    )
    def test_stays_behind_coming_soon_gate(self):
        response = self.client.get(reverse("install_app"))
        self.assertTemplateUsed(response, "core/coming_soon.html")
        self.assertTemplateNotUsed(response, "core/install_app.html")
