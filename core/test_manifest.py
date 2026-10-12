from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse


class ManifestTests(TestCase):
    def test_returns_manifest_json(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = response.json()
        self.assertEqual(data["name"], settings.SITE_NAME)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")

    def test_includes_android_install_icons(self):
        icons = self.client.get(reverse("manifest")).json()["icons"]
        sizes = {icon["sizes"] for icon in icons}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        self.assertIn("maskable", {icon["purpose"] for icon in icons})

    def test_served_without_language_prefix(self):
        self.assertEqual(reverse("manifest"), "/manifest.webmanifest")

    @override_settings(COMING_SOON=True)
    def test_passes_coming_soon_gate(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response["Content-Type"], "application/manifest+json")

    def test_linked_from_pages(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'rel="manifest" href="/manifest.webmanifest"')
        self.assertContains(response, "icons/apple-touch-icon-180.png")
