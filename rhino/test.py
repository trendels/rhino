"""
Utilities for testing.
"""
from __future__ import absolute_import

from collections import namedtuple
from StringIO import StringIO
from urllib import urlencode
from wsgiref.headers import Headers
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

from .resource import handler_metadata


# mock.assert_has_calls([]) is always True
def assert_mock_has_no_calls(mock):
    assert mock.mock_calls == []


def make_handler_metadata(verb=None, view=None, **kw):
    return handler_metadata.create(verb=verb, view=view, **kw)


class wsgi_response(namedtuple('wsgi_response', 'status headers body')):
    @property
    def code(self):
        return int(self.status.split(' ', 1)[0])


class TestClient(object):
    """Wraps a WSGI application under test.

    Provides helpers to pass requests to the application and inspect the
    response.
    """

    def __init__(self, app):
        self.app = app

    def request(self, method, path, environ=None, **kw):
        """Send a request to the application under test.

        The environment will be populated with some default keys. Additional
        keyword arguments will be interpreted as request headers.

        For example, passing x_foo=1 will add a request header "X-Foo: 1".
        """
        if environ is None:
            environ = {}
        # setup_testing_defaults() uses '127.0.0.1', but localhost is easier
        # to type when testing.
        environ.setdefault('SERVER_NAME', 'localhost')
        environ.setdefault('QUERY_STRING', '')  # silence validator warning
        setup_testing_defaults(environ)
        environ['REQUEST_METHOD'] = method
        environ['PATH_INFO'] = path
        for k, v in kw.items():
            key = k.upper()
            if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                key = 'HTTP_' + key
            environ[key] = str(v)
        start_response_rv = []

        def start_response(status, headers, exc_info=None):
            # TODO handle exc_info != None
            start_response_rv.extend([status, headers])

        wsgi_app = validator(self.app)
        app_iter = wsgi_app(environ, start_response)
        try:
            body = ''.join(app_iter)
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()
        statusline, headerlist = start_response_rv
        return wsgi_response(statusline, Headers(headerlist), body)

    def get(self, path_info, environ=None, **kw):
        """Send a GET request to the application."""
        return self.request('GET', path_info, environ, **kw)

    def post(self, path_info, body, content_type=None, environ=None, **kw):
        """Send a POST request to the application.

        If body is a dictionary, it will we submitted as a form with
        content_type='application/x-www-form-urlencoded'. Otherwise,
        the content_type parameter is required."""
        if environ is None:
            environ = {}
        if isinstance(body, dict):
            body = urlencode(body)
            content_type = 'application/x-www-form-urlencoded'
        elif content_type is None:
            raise ValueError("Can't send data without content_type")
        environ.update({
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': StringIO(body),
        })
        return self.request('POST', path_info, environ, **kw)

    def put(self, path_info, body, content_type, environ=None, **kw):
        """Send a PUT request to the application."""
        if environ is None:
            environ = {}
        environ.update({
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': StringIO(body),
        })
        return self.request('PUT', path_info, environ, **kw)

    def head(self, path_info, environ=None, **kw):
        """Send a HEAD request to the application."""
        return self.request('HEAD', path_info, environ, **kw)

    def options(self, path_info, environ=None, **kw):
        """Send an OPTIONS request to the application."""
        return self.request('OPTIONS', path_info, environ, **kw)

    def delete(self, path_info, environ=None, **kw):
        """Send a DELETE request to the application."""
        return self.request('DELETE', path_info, environ, **kw)
