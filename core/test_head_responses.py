"""
HEAD responses carry no body (#64). Django's test client strips HEAD bodies
itself, so these tests use the middleware and the WSGI handler directly.
"""

import tempfile

from asgiref.sync import iscoroutinefunction
from django.core.handlers.wsgi import WSGIHandler
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseNotModified,
    StreamingHttpResponse,
)
from django.test import (
    AsyncRequestFactory,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import path

from core.middleware import HeadResponseMiddleware


def wsgi_request(method, url):
    """
    Run one request through Django's WSGI handler as gunicorn does,
    closing the response afterwards. Returns status line, headers, body.
    """
    environ = RequestFactory().generic(method, url).environ
    started = {}

    def start_response(line, headers):
        started["line"], started["headers"] = line, dict(headers)

    result = WSGIHandler()(environ, start_response)
    try:
        body = b"".join(result)
    finally:
        result.close()
    return started["line"], started["headers"], body


class HeadResponseMiddlewareTests(SimpleTestCase):
    def run_middleware(self, method, response):
        request = getattr(RequestFactory(), method.lower())("/x/")
        return HeadResponseMiddleware(lambda request: response)(request)

    def test_head_body_removed_and_length_counted_when_missing(self):
        response = self.run_middleware("HEAD", HttpResponse("ok"))
        self.assertEqual(response.content, b"")
        self.assertEqual(response["Content-Length"], "2")

    def test_length_set_earlier_is_kept(self):
        early = HttpResponse("")
        early["Content-Length"] = "5120"  # e.g. a view answering HEAD itself
        response = self.run_middleware("HEAD", early)
        self.assertEqual(response["Content-Length"], "5120")

    def test_not_modified_is_left_alone(self):
        response = self.run_middleware("HEAD", HttpResponseNotModified())
        self.assertNotIn("Content-Length", response)

    def test_get_untouched(self):
        response = self.run_middleware("GET", HttpResponse("ok"))
        self.assertEqual(response.content, b"ok")


class AsyncHeadResponseMiddlewareTests(SimpleTestCase):
    """Under ASGI the middleware runs async instead of being adapted."""

    async def test_async_chain_head_body_removed(self):
        async def get_response(request):
            return HttpResponse("ok")

        middleware = HeadResponseMiddleware(get_response)
        self.assertTrue(iscoroutinefunction(middleware))
        response = await middleware(AsyncRequestFactory().head("/x/"))
        self.assertEqual(response.content, b"")
        self.assertEqual(response["Content-Length"], "2")

    async def test_async_streaming_stays_async_and_empty(self):
        async def chunks():
            yield b"secret"

        async def get_response(request):
            return StreamingHttpResponse(chunks())

        middleware = HeadResponseMiddleware(get_response)
        response = await middleware(AsyncRequestFactory().head("/x/"))
        self.assertTrue(response.is_async)
        self.assertEqual([chunk async for chunk in response.streaming_content], [])

    def test_sync_chain_stays_sync(self):
        middleware = HeadResponseMiddleware(lambda request: HttpResponse("ok"))
        self.assertFalse(iscoroutinefunction(middleware))


FILE_CONTENT = b"x" * 1000
opened = []


def file_view(request):
    file = tempfile.TemporaryFile()
    file.write(FILE_CONTENT)
    file.seek(0)
    opened.append(file)
    return FileResponse(file)


urlpatterns = [path("file/", file_view)]


@override_settings(ROOT_URLCONF=__name__)
class StreamingHeadThroughWsgiTests(TestCase):
    def setUp(self):
        opened.clear()

    def test_head_sends_nothing_and_closes_the_file(self):
        line, headers, body = wsgi_request("HEAD", "/file/")
        self.assertTrue(line.startswith("200"))
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], str(len(FILE_CONTENT)))
        self.assertTrue(opened[0].closed)

    def test_get_still_streams_the_file(self):
        _, _, body = wsgi_request("GET", "/file/")
        self.assertEqual(body, FILE_CONTENT)
        self.assertTrue(opened[0].closed)
