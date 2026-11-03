from unittest import mock

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.test_head_responses import wsgi_request


class HealthTests(TestCase):
    def test_ok_when_database_answers(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertIn("no-cache", response["Cache-Control"])

    def test_head_allowed_for_uptime_monitors(self):
        response = self.client.head(reverse("health"))
        self.assertEqual(response.status_code, 200)

    def test_head_through_wsgi_has_no_body(self):
        # The test client strips HEAD bodies itself; gunicorn doesn't (#64)
        line, headers, body = wsgi_request("HEAD", reverse("health"))
        self.assertTrue(line.startswith("200"))
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], "2")

    def test_post_not_allowed(self):
        response = self.client.post(reverse("health"))
        self.assertEqual(response.status_code, 405)

    def test_503_when_database_is_down(self):
        with mock.patch("core.views.connection.cursor", side_effect=DatabaseError):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)

    @override_settings(COMING_SOON=True)
    def test_passes_coming_soon_gate(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.content, b"ok")
