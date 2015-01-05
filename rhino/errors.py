from __future__ import absolute_import

from cgi import escape

from .http import status_codes
from .response import Response

__all__ = [
    'HTTPException',
    'Redirection',
    'ClientError',
    'ServerError',
    'MovedPermanently',
    'Found',
    'SeeOther',
    'TemporaryRedirect',
    'BadRequest',
    'Unauthorized',
    'Forbidden',
    'NotFound',
    'MethodNotAllowed',
    'NotAcceptable',
    'Gone',
    'UnsupportedMediaType',
    'InternalServerError',
]

# Default HTML error page, inspired by Django.
html_template = '''<!DOCTYPE html>
<html>
  <head>
    <title>%(status)s</title>
    <style type="text/css">
      html { font-family: sans-serif; font-size: small; color: #333; }
      html, body { margin: 0; padding: 0; }
      body > * { margin: 0; padding: 10px; }
      h1 { font-size: 180%%; font-weight: normal; background: wheat; border-bottom: 1px solid #ccc; }
      h1 small { font-size: 60%%; color: #777; }
      p { background: #eee; border-bottom: 1px solid #ccc; }
      p + p { background: #fff; border: 0; }
    </style>
  </head>
  <body>
    <h1>%(status)s <small>(%(code)s)</small></h1>
    <p>%(message)s</p>
    <p>%(details)s</p>
  </body>
</html>
'''

class HTTPException(Exception):
    """Base class for HTTP Exceptions

    Class variables:

    code
      : The status code (int)
    message
      : If present, an HTML error page will be sent that contains this message.
        The contents of `message` will be HTML-escaped.

    Instance properties:

    response
      : The `rhino.Response` instance that will be sent to the client.

    The constructor takes one argument, an optional message that will replace
    the default message. Subclasses can override the constructor to require
    error-specific arguments.
    """
    code = 500
    message = None
    details = None  # TODO for displaying structured error data in debug mode

    def __init__(self, message=None):
        if message is None:
            message = self.message
        if message is not None:
            body = html_template % {
                'code': self.code,
                'status': status_codes.get(self.code, "Unknown"),
                'message': escape(message),
                'details': self.details or '',
            }
            headers = [('Content-Type', 'text/html')]
        else:
            body, headers = '', []
        self.response = Response(self.code, body=body, headers=headers)


class Redirection(HTTPException):
    """Base class for redirections (3xx)."""
    pass

class ClientError(HTTPException):
    """Base class for client errors (4xx)."""
    pass

class ServerError(HTTPException):
    """Base class for server errors (5xx)."""
    pass


class MovedPermanently(Redirection):
    """301 Moved Permanently.

    Required arguments:

    location
      : The value for the Location header.
    """
    code = 301

    def __init__(self, location):
        super(MovedPermanently, self).__init__()
        self.response.headers['Location'] = location


class Found(Redirection):
    """302 Found.

    Required arguments:

    location
      : The value for the Location header.
    """
    code = 302

    def __init__(self, location):
        super(Found, self).__init__()
        self.response.headers['Location'] = location


class SeeOther(Redirection):
    """303 See Other.

    Required arguments:

    location
      : The value for the Location header.
    """
    code = 303

    def __init__(self, location):
        super(SeeOther, self).__init__()
        self.response.headers['Location'] = location


class TemporaryRedirect(Redirection):
    """307 Temporary Redirect.

    Required arguments:

    location
      : The value for the Location header.
    """
    code = 307

    def __init__(self, location):
        super(TemporaryRedirect, self).__init__()
        self.response.headers['Location'] = location


class BadRequest(ClientError):
    """400 Bad Request."""
    code = 400
    message = 'The server could not understand the request.'


class Unauthorized(ClientError):
    """401 Unauthorized.

    Required arguments:

    scheme
      : The authentication scheme to use, e.g. 'Basic'.

    **params
      : Parameters for the WWW-Authenticate header, e.g. `realm="my website"`.
    """
    code = 401

    def __init__(self, scheme, **params):
        super(Unauthorized, self).__init__()
        param_str = ', '.join(['%s="%s"' % (k, v)
                               for k, v in sorted(params.items())])
        www_authenticate = "%s %s" % (scheme, param_str)
        self.response.headers['WWW-Authenticate'] = www_authenticate


class Forbidden(ClientError):
    """403 Forbidden."""
    code = 403
    message = 'The server is refusing to fulfill the request.'


class NotFound(ClientError):
    """404 NotFound."""
    code = 404
    message = 'The requested resource could not be found.'


class MethodNotAllowed(ClientError):
    """405 Method Not Allowed.

    Required arguments:

    allow
      : The value for the 'Allow' header (A list of comma-separated HTTP
        method names).
    """
    code = 405
    message = 'The request method is not allowed for this resource.'

    def __init__(self, allow):
        super(MethodNotAllowed, self).__init__()
        self.response.headers['Allow'] = allow


class NotAcceptable(ClientError):
    """406 Not Acceptable."""
    code = 406
    message = 'The resource is not capable of generating a response entity in an acceptable format.'


class Gone(ClientError):
    """410 Gone."""
    code = 410
    message = 'The requested resource is no longer available.'
    details = """
        <q style="font-style: italic; quotes: none;">Embracing HTTP error code
        410 means embracing the impermanence of all things.</q> &mdash; Mark
        Pilgrim
    """

class UnsupportedMediaType(ClientError):
    """415 Unsupported Media Type."""
    code = 415
    message = 'The request entity is in a format that is not supported by this resource.'


class InternalServerError(ServerError):
    """500 Internal Server Error."""
    code = 500
    message = 'The server encountered an error while processing the request.'
