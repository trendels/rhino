from __future__ import absolute_import

import cgi
import collections
import urllib
import urlparse
from Cookie import SimpleCookie
from StringIO import StringIO
from wsgiref.util import request_uri, application_uri

from .urls import request_context, build_url

__all__ = [
    'Request',
    'RequestHeaders',
    'QueryDict',
    'WsgiInput',
]


class RequestHeaders(collections.Mapping):
    """A dictionary-like object to access request headers.

    Keys are case-insensitive.
    """

    def __init__(self, environ, encoding='latin-1'):
        self.environ = environ
        self.encoding = encoding

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

    def __getitem__(self, key):
        return self.environ[self._key(key)].decode(self.encoding)

    def __iter__(self):
        return (self._name(k) for k in self._keys())

    def __len__(self):
        return len(self._keys())


class QueryDict(collections.Mapping):
    """A dictionary-like object to access query parameters.

    Accessing a key returns the first value for that key.
    The keys(), values() and items() methods will return a key/value multiple
    times, if it is present multiple times in the query string.

    The getall() method can be used to return all values for a given key.
    """

    def __init__(self, items):
        self._items = items

    def __getitem__(self, key):
        for k, v in self._items:
            if k == key:
                return v
        raise KeyError(key)

    def __iter__(self):
        return (k for k, v in self._items)

    def __len__(self):
        return len(self._items)


    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        return True

    def getall(self, key):
        """Return a list of values for the given key."""
        return [v for k, v in self._items if k == key]

    getlist = getall

    def keys(self):
        return [k for k, v in self._items]

    def values(self):
        return [v for k, v in self._items]

    def items(self):
        return self._items[:]

    def itervalues(self):
        return (v for k, v in self._items)

    def iteritems(self):
        return ((k, v)  for k, v in self._items)


# Implementation taken from gevent.pywsgi.Input
class WsgiInput(object):
    """Represents a WSGI input filehandle that is safe to use read() on"""
    def __init__(self, rfile, content_length=None):
        self.rfile = rfile
        self.content_length = content_length
        self.bytes_read = 0

    def _do_read(self, size=None, use_readline=False):
        reader = self.rfile.readline if use_readline else self.rfile.read
        if self.content_length is None:
            return ''
        bytes_left = self.content_length - self.bytes_read
        if size is None:
            size = bytes_left
        elif size > bytes_left:
            size = bytes_left
        if not size:
            return ''
        chunk = reader(size)
        self.bytes_read += len(chunk)
        if len(chunk) < size:
            if (use_readline and not chunk.endswith('\n')) or not use_readline:
                raise IOError("unexpected end of file while reading request at position %s" % self.bytes_read)
        return chunk

    def read(self, size=None):
        return self._do_read(size)

    def readline(self, size=None):
        return self._do_read(size, use_readline=True)

    def readlines(self, hint=None):
        return list(self)

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line


class Request(object):
    """Represents an HTTP request built from a WSGI environment.

    Class variables:

    wrap_wsgi_input
      : When `True` (the default), `Request.input` returns
        `environ['wsgi.input']` wrapped in `WsgiInput`, to make it safe to call
        `read()` on it without providing the content length. This is required
        for servers like `wsgiref.simple_server`, which is also used by
        `Rhino.mapper.start_server()`.

        Some WSGI servers (e.g. `gevent.pywsgi`) provide a safe `wsgi.input`
        that also supports chunked encoding (a.k.a streamed uploads). To
        be able to benefit from this functionality, `wrap_wsgi_input` needs
        to be set to `False`. Alternatively, the original input file can
        always be found in `Request.environ['wsgi.input']`.
    """
    wrap_wsgi_input = True

    def __init__(self, environ):
        environ.setdefault('wsgiorg.routing_args', ([], {}))
        self.environ = environ
        self.headers = RequestHeaders(environ)
        self._url = None
        self._input = None
        self._body = None
        self._form = None
        self._query = None
        self._cookies = None
        self._context = []
        self._application_uri = None
        self._body_reader = None

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
        self, target, args = args[0], args[1], list(args[2:])
        query = kw.pop('_query', None)
        relative = kw.pop('_relative', False)
        url = build_url(self._context, target, args, kw)
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
                for k, v in urlparse.parse_qsl(
                    query_string, keep_blank_values=True)
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
        """The value of the Content-Length header as an integer, or None"""
        try:
            return int(self.environ['CONTENT_LENGTH'])
        except (KeyError, ValueError):
            return None

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

    @property
    def input(self):
        """Returns a file-like object representing the request body."""
        if self._input is None:
            input_file = self.environ['wsgi.input']
            if self.wrap_wsgi_input:
                content_length = self.content_length or 0
                self._input = WsgiInput(input_file, self.content_length)
            else:
                self._input = input_file
        return self._input

    @property
    def body(self):
        """Reads and returns the entire request body.

        On first access, reads `content_length` bytes from `input` and stores
        the result on the request instance. On subsequent access, returns the
        cached value.
        """
        if self._body is None:
            if self._body_reader is None:
                self._body = self.input.read(self.content_length or 0)
            else:
                self._body = self._body_reader(self.input)
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
            # Make sure calling input.read() or accessing .body
            # doesn't read from 'wsgi.input' anymore, as it's been depleted
            # already.
            self._input = StringIO('')
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
