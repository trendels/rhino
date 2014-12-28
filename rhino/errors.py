from __future__ import absolute_import

from cgi import escape

from .http import status_codes
from .response import Response

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


class Redirection(HTTPException): pass
class ClientError(HTTPException): pass
class ServerError(HTTPException): pass


class MovedPermanently(Redirection):
    code = 301

    def __init__(self, location):
        super(MovedPermanently, self).__init__()
        self.response.headers['Location'] = location


class Found(Redirection):
    code = 302

    def __init__(self, location):
        super(Found, self).__init__()
        self.response.headers['Location'] = location


class SeeOther(Redirection):
    code = 303

    def __init__(self, location):
        super(SeeOther, self).__init__()
        self.response.headers['Location'] = location


class TemporaryRedirect(Redirection):
    code = 307

    def __init__(self, location):
        super(TemporaryRedirect, self).__init__()
        self.response.headers['Location'] = location


class BadRequest(ClientError):
    code = 400
    message = 'The server could not understand the request.'


class Unauthorized(ClientError):
    code = 401

    def __init__(self, scheme, **params):
        super(Unauthorized, self).__init__()
        param_str = ', '.join(['%s="%s"' % (k, v) for k, v in params.items()])
        www_authenticate = "%s %s" % (scheme, param_str)
        self.response.headers['WWW-Authenticate'] = www_authenticate


class Forbidden(ClientError):
    code = 403
    message = 'The server is refusing to fulfill the request.'


class NotFound(ClientError):
    code = 404
    message = 'The requested resource could not be found.'


class MethodNotAllowed(ClientError):
    code = 405
    message = 'The request method is not allowed for this resource.'

    def __init__(self, allow, *args, **kw):
        super(MethodNotAllowed, self).__init__(*args, **kw)
        self.response.headers['Allow'] = allow


class NotAcceptable(ClientError):
    code = 406
    message = 'The resource is not capable of generating a response entity in an acceptable format.'


class Gone(ClientError):
    code = 410
    message = 'The requested resource is no longer available.'
    details = """
        <q style="font-style: italic; quotes: none;">Embracing HTTP error code
        410 means embracing the impermanence of all things.</q> &mdash; Mark
        Pilgrim
    """

class UnsupportedMediaType(ClientError):
    code = 415
    message = 'The request entity is in a format that is not supported by this resource.'


class InternalServerError(ServerError):
    code = 500
    message = 'The server encountered an error while processing the request.'
