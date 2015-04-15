from __future__ import absolute_import

import collections
import urllib
import urlparse
import time
from Cookie import SimpleCookie
from datetime import datetime, timedelta
from wsgiref.headers import Headers as ResponseHeaders
from wsgiref.util import application_uri

from .http import httpdate_to_timestamp, datetime_to_httpdate, \
        timedelta_to_httpdate, total_seconds, match_etag, status_codes

__all__ = [
    'Response',
    'Entity',
    'response',
    'ok',
    'created',
    'no_content',
    'redirect',
]

# Include: etag, content-location, expires, cache-control, vary
# TODO The revised HTTP RFCs (rfcs 7230-7235) have removed the distinction
# between entity-headers and other headers. We might need to revisit this.
entity_headers = set('''
       Allow Content-Encoding Content-Language Content-Length Content-Location
       Content-MD5 Content-Range Content-Type Expires Last-Modified
    '''.lower().split())

_include_in_304 = set('''
        Date ETag Content-Location Expires Cache-Control Vary
    '''.lower().split())

_filter_from_304 = entity_headers - _include_in_304


def filter_304_headers(headers):
    """Filter a list of headers to include in a "304 Not Modified" response."""
    return [(k, v) for k, v in headers if k.lower() not in _filter_from_304]


class Entity(object):
    """Represents a response body with entity headers."""

    def __init__(self, body, **kw):
        self.body = body
        self.headers = response(200, **kw).headers


class ResponseBody(object):
    """A WSGI response iterator.

    Holds the response body and a list of callbacks to be called when the
    response is closed by the WSGI server.
    """

    def __init__(self, body, callbacks=None):
        if callbacks is None:
            callbacks = []
        if not hasattr(body, '__iter__'):
            body = iter([body])
        self.callbacks = callbacks
        self.body = body

    def __iter__(self):
        return self

    def next(self):
        return next(self.body)

    def close(self):
        for fn in self.callbacks:
            fn()


class Response(object):
    """Represents an HTTP response.

    Class attributes:

    default_encoding
      : When finalizing the response and the response body is a unicode string,
        it is encoded using default_encoding (default: 'utf-8')

    default_content_type
      : When finalizing the response and the response body is not empty this is
        used as the default value for the Content-Type header, if none is
        provided (default: 'text/plain; charset=utf-8')
    """
    default_encoding = 'utf-8'
    default_content_type = 'text/plain; charset=utf-8'

    def __init__(self, code, headers=None, body=''):
        """Create a new HTTP response.

        Parameters:

        code
          : an integer status code.

        headers
          : a list of response headers as (name, value) tuples.

        body
          : a value for the response body.
            The body is only validated when the request is finalized
            (in `__call__`).

            Valid values for the response body are:

            The empty string ('')
              : This indicates an empty response body.

            A str or unicode object
              : Sent as-is, after encoding unicode using default_encoding.

            An iterator that yields str or unicode objects
              : The response is streamed to the client using chunked
                transfer-encoding (when implemented by the WSGI server).

            A callable that returns a single str or unicode object
              : This is only useful in combination with an 'ETag' or
                'Last-Modified' header, to delay construction of the
                response body until after conditional request handling
                has taken place, and no "304 Not Modified" response has
                been sent.

            An Entity instance
              : The response body (which must be of one of the types listed
                above) will be taken from the entity instance, and any entity
                headers will be added to the response headers, with existing
                headers of the same name taking precedence.
        """
        headers = ResponseHeaders(headers or [])

        if isinstance(body, Entity):
            entity = body
            body = entity.body
            # Response headers override entity headers
            for k, v in entity.headers.items():
                headers.setdefault(k, v)

        self._code = code
        self._headers = headers
        self._body = body
        self._callbacks = []

    @property
    def code(self):
        """The HTTP status code as an integer."""
        return self._code

    @property
    def headers(self):
        """A `wsgiref.headers.Headers` instance."""
        return self._headers

    @property
    def body(self):
        """The response body."""
        return self._body

    @body.setter
    def body(self, value):
        self._body = value

    @property
    def status(self):
        """The status line as a string (status code + reason)"""
        reason = status_codes.get(self.code, "Unknown")
        return "%s %s" % (self._code, reason)

    def add_callback(self, fn):
        """Add a callback to be executed when the response is closed."""
        self._callbacks.append(fn)

    def set_cookie(self, key, value='', max_age=None, path='/', domain=None,
                   secure=False, httponly=False, expires=None):
        """Set a response cookie.

        Parameters:

        key
          : The cookie name.
        value
          : The cookie value.
        max_age
          : The maximum age of the cookie in seconds, or as a
            datetime.timedelta instance.
        path
          : Restrict the cookie to this path (default: '/').
        domain
          : Restrict the cookie to his domain.
        secure
          : When True, instruct the client to only sent the cookie over HTTPS.
        httponly
          : When True, instruct the client to disallow javascript access to
            the cookie.
        expires
          : Another way of specifying the maximum age of the cookie. Accepts
            the same values as max_age (number of seconds, datetime.timedelta).
            Additionaly accepts a datetime.datetime instance.
            Note: a value of type int or float is interpreted as a number of
            seconds in the future, *not* as Unix timestamp.
        """
        key, value = key.encode('utf-8'), value.encode('utf-8')
        cookie = SimpleCookie({key: value})
        m = cookie[key]
        if max_age is not None:
            if isinstance(max_age, timedelta):
                m['max-age'] = int(total_seconds(max_age))
            else:
                m['max-age'] = int(max_age)
        if path is not None: m['path'] = path.encode('utf-8')
        if domain is not None: m['domain'] = domain.encode('utf-8')
        if secure: m['secure'] = True
        if httponly: m['httponly'] = True
        if expires is not None:
            # 'expires' expects an offset in seconds, like max-age
            if isinstance(expires, datetime):
                expires = total_seconds(expires - datetime.utcnow())
            elif isinstance(expires, timedelta):
                expires = total_seconds(expires)
            m['expires'] = int(expires)

        self.headers.add_header('Set-Cookie', m.OutputString())

    def delete_cookie(self, key, path='/', domain=None):
        """Delete a cookie (by setting it to a blank value).

        The path and domain values must match that of the original cookie.
        """
        self.set_cookie(key, value='', max_age=0, path=path, domain=domain,
                        expires=datetime.utcfromtimestamp(0))

    def conditional_to(self, request):
        """Return a response that is conditional to a given request.

        Returns the Response instance unchanged, or a new Response instance
        with a "304 Not Modified" status code.
        """
        if not self.code == 200:
            return self

        request_headers = request.headers
        response_headers = self.headers

        if_none_match = request_headers.get('If-None-Match')
        if_modified_since = request_headers.get('If-Modified-Since')

        etag_ok, date_ok = False, False

        if if_none_match:
            etag = response_headers.get('ETag')
            if etag and match_etag(etag, if_none_match, weak=True):
                etag_ok = True

        if if_modified_since:
            last_modified = response_headers.get('Last-Modified')
            if last_modified:
                try:
                    modified_ts = httpdate_to_timestamp(last_modified)
                    last_valid_ts = httpdate_to_timestamp(if_modified_since)
                    if modified_ts <= last_valid_ts:
                        date_ok = True
                except:
                    pass

        if if_none_match and not etag_ok:
            return self
        elif if_modified_since and not date_ok:
            return self
        elif etag_ok or date_ok:
            headers = filter_304_headers(self.headers.items())
            if 'Date' not in self.headers:
                headers.append(('Date', datetime_to_httpdate(time.time())))
            return Response(code=304, headers=headers, body='')
        return self

    def __call__(self, environ, start_response):
        """WSGI interface

        Finalizes the response body, calls `start_response` and returns a
        response iterator.
        """
        code = self._code
        headers = self._headers
        body = self._body
        request_method = environ.get('REQUEST_METHOD', '').upper()

        # Resolve lazy response body
        if callable(body):
            body = body()

        # Validate response body
        if isinstance(body, unicode):
            body = body.encode(self.default_encoding)
        elif isinstance(body, collections.Iterator):
            body = (s.encode(self.default_encoding)
                    if isinstance(s, unicode) else s
                    for s in body)
        elif not isinstance(body, str):
            raise TypeError("response body must be of type unicode, str,"
                            " or Iterator, not '%s'" % type(body))

        # Make sure we have Content-Type and Content-Length headers if needed.
        if code != 304:
            if 'Content-Type' not in headers:
                headers['Content-Type'] = self.default_content_type
            if type(body) is str and 'Content-Length' not in headers:
                headers['Content-Length'] = str(len(body))

        # Special case for Location header: accept unicode, make absolute.
        location = headers.get('Location')
        if location is not None:
            if isinstance(location, unicode):
                location = location.encode('utf-8')
            headers['Location'] = urlparse.urljoin(
                application_uri(environ),
                urllib.quote(location, safe=';/?:@&=+$,#')
            )

        # Send response
        header_list = [(k.encode('ascii'), v.encode('latin-1'))
                       for k, v in headers.items()]
        if code in (204, 304) or request_method == 'HEAD':
            body = ''

        start_response(self.status, header_list)
        return ResponseBody(body, self._callbacks)


def response(code, body='', etag=None, last_modified=None, expires=None, **kw):
    """Helper to build an HTTP response.

    Parameters:

    code
     :  An integer status code.
    body
     :  The response body. See `Response.__init__` for details.
    etag
     :  A value for the ETag header. Double quotes will be added unless the
        string starts and ends with a double quote.
    last_modified
     :  A value for the Last-Modified header as a datetime.datetime instance
        or Unix timestamp.
    expires
     :  A value for the Expires header as number of seconds, datetime.timedelta
        or datetime.datetime instance.
        Note: a value of type int or float is interpreted as a number of
        seconds in the future, *not* as Unix timestamp.
    **kw
     :  All other keyword arguments are interpreted as response headers.
        The names will be converted to header names by replacing
        underscores with hyphens and converting to title case
        (e.g. `x_powered_by` => `X-Powered-By`).

    """
    if etag is not None:
        if not (etag[0] == '"' and etag[-1] == '"'):
            etag = '"%s"' % etag
        kw['etag'] = etag

    if last_modified is not None:
        kw['last_modified'] = datetime_to_httpdate(last_modified)

    if expires is not None:
        if isinstance(expires, datetime):
            kw['expires'] = datetime_to_httpdate(expires)
        else:
            kw['expires'] = timedelta_to_httpdate(expires)

    headers = [(k.replace('_', '-').title(), v) for k, v in sorted(kw.items())]
    return Response(code, headers, body)


def ok(body='', code=200, **kw):
    """Shortcut for response(200, ...).

    The status code must be in the 2xx range."""
    if not 200 <= code < 300:
        raise ValueError("Not a 2xx status code: '%s'" % code)
    return response(code=code, body=body, **kw)


def created(body='', **kw):
    """Shortcut for response(201, ...)."""
    return response(code=201, body=body, **kw)


def no_content(**kw):
    """Shortcut for response(204, body='', ...)."""
    return response(code=204, body='', **kw)


def redirect(location, code=302, **kw):
    """Shortcut for response(302, location=location, ...)

    The status code must be in the 3xx range."""
    if not 300 <= code < 400:
        raise ValueError("Not a 3xx status code: '%s'" % code)
    return response(code=code, location=location, **kw)
