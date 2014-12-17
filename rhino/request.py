from __future__ import absolute_import

import cgi
import urllib
import urlparse
from Cookie import SimpleCookie
from wsgiref.util import request_uri, application_uri

from .urls import request_context, build_url


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

    def __contains__(self, name):
        try:
            self[name]
        except KeyError:
            return False
        return True

    def __getitem__(self, name):
        v = self.get(name, _default)
        if v is _default:
            raise KeyError(name)
        return v

    def get_all(self, name):
        return [v for k, v in self._items if k == name]

    def get(self, name, default=None):
        for k, v in self._items:
            if k == name:
                return v
        return default

    def keys(self):
        return [k for k, v in self._items]

    def values(self):
        return [v for k, v in self._items]

    def items(self):
        return self._items[:]


_callback_phases = ['enter', 'leave', 'finalize', 'teardown', 'close']

def _callback_dict():
    return dict((k, []) for k in _callback_phases)


class Request(object):
    """Represents an HTTP request built from a WSGI environment."""

    def __init__(self, environ):
        self.environ = environ
        self.headers = RequestHeaders(environ)
        self._url = None
        self._body = None
        self._form = None
        self._query = None
        self._cookies = None
        self._context = []
        self._application_uri = None
        self._callbacks = _callback_dict()

    def _add_context(self, **kw):
        self._context.append(request_context(**kw))

    def _set_context(self, **kw):
        if not self._context:
            raise ValueError("No routing context present.")
        self._context[-1] = self._context[-1]._replace(**kw)

    def add_callback(self, phase, fn):
        """Add a callback to run in a specific phase.

        Possible values for phase:

            Phase       Callback arguments  Description of where and when it is called
            =======================================================================================================
            'enter'     request             In resource, after handler has been resolved but before it is run
            'leave'     request, response   In resource, after handler has returned successfully
            'finalize'  request, response   In mapper, before response body and headers are finalized
            'teardown'  -                   In mapper, before WSGI response is returned
            'close'     -                   In the WSGI server, when it calls close() on the WSGI response iterator

        """
        try:
            self._callbacks[phase].append(fn)
        except KeyError:
            raise KeyError("Invalid callback phase '%s'. Must be one of %s" % (phase, _callback_phases))

    def _run_callbacks(self, phase, *args):
        for fn in self._callbacks[phase]:
            fn(*args)

    def url_for(*args, **kw):
        """Build the URL for a target.

        Special keyword arguments:

        _query:
            Append query string (dict or list of tuples)

        _absolute:
            When False, build relative URLs (default: True)

        All other keyword arguments are treated as URL parameters.
        """
        # Allow passing 'self' as named parameter
        self, target = args
        query = kw.pop('_query', None)
        absolute = kw.pop('_absolute', True)
        url = build_url(self._context, target, kw)
        if query:
            if isinstance(query, dict):
                query = sorted(query.items())
            url = url + '?'+ urllib.urlencode(query)
        if absolute:
            if self._application_uri is None:
                self._application_uri = application_uri(self.environ)
            url = urlparse.urljoin(self._application_uri, url)
        return url

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
        """The reconstructed request URI (absolute)."""
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
        """The remote hosts's port number as an integer, or None (REMOTE_PORT)."""
        port = self.environ.get('REMOTE_PORT')
        return int(port) if port is not None else None

    @property
    def scheme(self):
        """The URL scheme, usually 'http' or 'https' (wsgi.url_scheme)."""
        return self.environ.get('wsgi.url_scheme')

    @property
    def routing_args(self):
        """Contains variables extracted from the URL (wsgiorg.routing_args)

        A pair of list/dict. The list is free for internal use by the
        application, while the dict contains the variables extracted from
        matching the request URL against the route template.
        These are passed to request handlers as ``*args`` and ``**kwargs``,
        respectively.
        """
        routing_args = self.environ.get('wsgiorg.routing_args')
        if routing_args is None:
            routing_args = ([], {})
            self.environ['wsgiorg.routing_args'] = routing_args
        return routing_args

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
        Parsing is done using the stdlib's cgi.FieldStorage which supports
        multipart forms (file uploads).
        Returns a QueryDict instance holding the form fields. Uploaded files
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
        """Returns a dictionary mapping cookie names to their value."""
        if self._cookies is None:
            c = SimpleCookie(self.environ.get('HTTP_COOKIE'))
            self._cookies = dict([
                (k.decode('utf-8'), v.value.decode('utf-8'))
                for k, v in c.items()
            ])
        return self._cookies
