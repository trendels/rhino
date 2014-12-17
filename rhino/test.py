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

from .resource import request_handler


def make_request_handler(name=None, verb=None, view=None, accepts='*/*', provides=None):
    return request_handler(name=name, verb=verb, view=view, accepts=accepts, provides=provides)


class wsgi_response(namedtuple('wsgi_response', 'status headers body')):
    @property
    def code(self):
        return int(self.status.split(' ', 1)[0])


class TestClient(object):
    def __init__(self, app):
        """Wraps a WSGI application under test and provides methods to interact
        with it."""
        self.app = app

    def request(self, method, path, environ=None, **kw):
        """Send a request to the application under test.

        The environment will be populated with some default keys. Additional
        headers can be passed as keyword arguments.
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
            if k not in ('content_type', 'content_length'):
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
        the content_type parameter is mandatory."""
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
