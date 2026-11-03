"""
HEAD responses carry no body (#64). Django's test client strips HEAD bodies
itself, so these tests use the middleware and the WSGI handler directly.
"""

from io import BytesIO

from django.core.handlers.wsgi import WSGIHandler
from django.http import FileResponse, HttpResponse
from django.test import RequestFactory, TestCase

from core.middleware import HeadResponseMiddleware


class HeadResponseMiddlewareTests(TestCase):
    def run_middleware(self, method, response):
        request = getattr(RequestFactory(), method.lower())("/x/")
        return HeadResponseMiddleware(lambda request: response)(request)

    def test_head_body_removed_and_length_kept(self):
        response = self.run_middleware("HEAD", HttpResponse("ok"))
        self.assertEqual(response.content, b"")
        self.assertEqual(response["Content-Length"], "2")

    def test_get_untouched(self):
        response = self.run_middleware("GET", HttpResponse("ok"))
        self.assertEqual(response.content, b"ok")

    def test_streaming_head_sends_nothing(self):
        file = BytesIO(b"x" * 1000)
        response = self.run_middleware("HEAD", FileResponse(file))
        self.assertEqual(b"".join(response.streaming_content), b"")
        response.close()  # as the server does after sending
        self.assertTrue(file.closed)


class HeadThroughWsgiTests(TestCase):
    """The real request path gunicorn uses, without the test client."""

    def wsgi(self, method, path):
        environ = RequestFactory().generic(method, path).environ
        status = {}

        def start_response(line, headers):
            status["line"], status["headers"] = line, dict(headers)

        body = b"".join(WSGIHandler()(environ, start_response))
        return status["line"], status["headers"], body

    def test_health_head_has_no_body(self):
        line, headers, body = self.wsgi("HEAD", "/health/")
        self.assertTrue(line.startswith("200"))
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], "2")

    def test_health_get_still_says_ok(self):
        line, _, body = self.wsgi("GET", "/health/")
        self.assertTrue(line.startswith("200"))
        self.assertEqual(body, b"ok")
