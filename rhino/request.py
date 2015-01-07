from __future__ import absolute_import

import cgi
import urllib
import urlparse
from Cookie import SimpleCookie
from wsgiref.util import request_uri, application_uri

from .urls import request_context, build_url

__all__ = [
    'Request',
    'RequestHeaders',
    'QueryDict',
]


class RequestHeaders(object):
    """A dictionary-like object to access request headers.

    Keys are case-insensitive. Accessing a header that is not present
    returns None instead of raising KeyError.
    """

    def __init__(self, environ):
        self.environ = environ

    @staticmethod
    def _key(name):
        key = name.upper().replace('-', '_')
        if key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            return key
        return 'HTTP_' + key

    @staticmethod
    def _name(key):
        if key[:5] == 'HTTP_':
            key = key[5:]
        return key.replace('_', '-').title()

    def _keys(self):
        return [k for k in self.environ
                if k[:5] == 'HTTP_' or k in ('CONTENT_TYPE', 'CONTENT_LENGTH')]

    def __len__(self):
        return len(self._keys())

    def __contains__(self, name):
        return self._key(name) in self.environ

    def get(self, name, default=None):
        value = self.environ.get(self._key(name), default)
        return default if value is default else value.decode('latin-1')

    def __getitem__(self, name):
        return self.get(name)

    def keys(self):
        return [self._name(k) for k in self._keys()]

    def values(self):
        return [self.environ[k].decode('latin-1') for k in self._keys()]

    def items(self):
        return [(self._name(k), self.environ[k].decode('latin-1'))
                for k in self._keys()]


_default = object()  # unique canary value, used by QueryDict.__getitem__


class QueryDict(object):
    """A dictionary-like object to access query parameters.

    Accessing a key returns the first value for that key.
    The keys(), values() and items() methods will return a key/value multiple
    times, if it is present multiple times in the query string.

    The get_all() method can be used to return all values for a given key.
    """

    def __init__(self, items):
        self._items = items

    def __len__(self):
        return len(self._items)

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        return True

    def __getitem__(self, key):
        v = self.get(key, _default)
        if v is _default:
            raise KeyError(key)
        return v

    def get_all(self, key):
        """Return a list of values for the given key."""
        return [v for k, v in self._items if k == key]

    def get(self, key, default=None):
        for k, v in self._items:
            if k == key:
                return v
        return default

    def keys(self):
        return [k for k, v in self._items]

    def values(self):
        return [v for k, v in self._items]

    def items(self):
        return self._items[:]


class Request(object):
    """Represents an HTTP request built from a WSGI environment."""

    def __init__(self, environ):
        environ.setdefault('wsgiorg.routing_args', ([], {}))
        self.environ = environ
        self.headers = RequestHeaders(environ)
        self._url = None
        self._body = None
        self._form = None
        self._query = None
        self._cookies = None
        self._context = []
        self._application_uri = None

    def _add_context(self, **kw):
        self._context.append(request_context(**kw))

    def _set_context(self, **kw):
        if not self._context:  # pragma: no cover
            raise RuntimeError("No routing context present.")
        self._context[-1] = self._context[-1]._replace(**kw)

    def url_for(*args, **kw):
        """Build the URL for a target route.

        The target is the first positional argument, and can be any valid
        target for `Mapper.path`, which will be looked up on the current
        mapper instance and used to build the URL for that route.
        Additionally, it can be one of:

        '.'
          : Builds the URL for the current route.

        '/'
          : Builds the URL for the root (top-most) mapper instance.

        '/a', '/a.b', etc.
          : Builds the URL for a named route relative to the root mapper.

        '.a', '..a', '..a.b', etc.
          : Builds a URL for a named route relative to the current mapper.
            Each additional leading '.' after the first one starts one
            level higher in the hierarchy of nested mappers (i.e. '.a' is
            equivalent to 'a').

        Special keyword arguments:

        `_query`
          : Append a query string to the URL (dict or list of tuples)

        `_relative`
          : When True, build a relative URL (default: False)

        All other keyword arguments are treated as parameters for the URL
        template.
        """
        # Allow passing 'self' as named parameter
        self, target = args
        query = kw.pop('_query', None)
        relative = kw.pop('_relative', False)
        url = build_url(self._context, target, kw)
        if query:
            if isinstance(query, dict):
                query = sorted(query.items())
            url = url + '?' + urllib.urlencode(query)
        if relative:
            return url
        else:
            if self._application_uri is None:
                self._application_uri = application_uri(self.environ)
            return urlparse.urljoin(self._application_uri, url)

    @property
    def method(self):
        """The HTTP request method (verb)."""
        return self.environ.get('REQUEST_METHOD', 'GET').upper()

    @property
    def script_name(self):
        """The SCRIPT_NAME environment key as a unicode string."""
        return self.environ.get('SCRIPT_NAME', '').decode('utf-8')

    @property
    def path_info(self):
        """The PATH_INFO environment key as a unicode string."""
        return self.environ.get('PATH_INFO', '').decode('utf-8')

    @property
    def query(self):
        """A QueryDict instance holding the query parameters (QUERY_STRING)."""
        if self._query is None:
            query_string = self.environ.get('QUERY_STRING')
            self._query = QueryDict([
                (k.decode('utf-8'), v.decode('utf-8'))
                for k, v in urlparse.parse_qsl(query_string)
            ])
        return self._query

    @property
    def url(self):
        """The reconstructed request URL (absolute)."""
        if self._url is None:
            self._url = request_uri(self.environ, include_query=1)
        return self._url

    @property
    def content_type(self):
        """The value of the Content-Type header, or None"""
        return self.environ.get('CONTENT_TYPE')

    @property
    def content_length(self):
        """The value of the Content-Length header as an integer, or 0"""
        try:
            return int(self.environ['CONTENT_LENGTH'])
        except (KeyError, ValueError):
            return 0

    @property
    def server_name(self):
        """The SERVER_NAME environment key"""
        return self.environ.get('SERVER_NAME')

    @property
    def server_port(self):
        """The server's port number as an integer, or None (SERVER_PORT)."""
        port = self.environ.get('SERVER_PORT')
        return int(port) if port is not None else None

    @property
    def server_protocol(self):
        """The SERVER_PROTOCOL environment key"""
        return self.environ.get('SERVER_PROTOCOL')

    @property
    def remote_addr(self):
        """The REMOTE_ADDR environment key"""
        return self.environ.get('REMOTE_ADDR')

    @property
    def remote_port(self):
        """The client's port number as an integer, or None (REMOTE_PORT)."""
        port = self.environ.get('REMOTE_PORT')
        return int(port) if port is not None else None

    @property
    def scheme(self):
        """The URL scheme, usually 'http' or 'https' (wsgi.url_scheme)."""
        return self.environ.get('wsgi.url_scheme')

    @property
    def routing_args(self):
        """Returns named parameters extracted from the URL during routing."""
        return self.environ['wsgiorg.routing_args'][1]

    # TODO more CGI variables? See: <http://web.archive.org/web/20131002054457/http://ken.coar.org/cgi/draft-coar-cgi-v11-03.txt>

    # TODO file-like object that reads no more than content_length bytes
    # from wsgi.environ
    @property
    def body(self):
        """Reads content_length bytes from wsgi.input and returns the result.

        Cached after first access."""
        if self._body is None:
            self._body = self.environ['wsgi.input'].read(self.content_length)
        return self._body

    @property
    def form(self):
        """Reads the request body and tries to parse it as a web form.

        Parsing is done using the stdlib's `cgi.FieldStorage` class
        which supports multipart forms (file uploads).
        Returns a `QueryDict` instance holding the form fields. Uploaded files
        are represented as form fields with a 'filename' attribute.
        """
        if self._form is None:
            environ = self.environ.copy()
            environ['QUERY_STRING'] = ''
            fs = cgi.FieldStorage(
                fp=self.environ['wsgi.input'],
                environ=environ,
                keep_blank_values=True)
            # File upload field handling copied from WebOb
            fields = []
            for f in fs.list or []:
                if f.filename:
                    f.filename = f.filename.decode('utf-8')
                    fields.append((f.name.decode('utf-8'), f))
                else:
                    fields.append(
                        (f.name.decode('utf-8'), f.value.decode('utf-8'))
                    )
            self._form = QueryDict(fields)
        return self._form

    @property
    def cookies(self):
        """Returns a dictionary mapping cookie names to their values."""
        if self._cookies is None:
            c = SimpleCookie(self.environ.get('HTTP_COOKIE'))
            self._cookies = dict([
                (k.decode('utf-8'), v.value.decode('utf-8'))
                for k, v in c.items()
            ])
        return self._cookies
