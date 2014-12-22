from __future__ import absolute_import

from .response import Response

class HTTPException(Exception):
    code = 500
    message = None

    def __init__(self):
        self.response = Response(self.code, body=self.message or '')


class Redirection(HTTPException): pass
class ClientError(HTTPException): pass
class ServerError(HTTPException): pass


class BadRequest(ClientError):
    code = 400
    message = 'The server could not understand the request.'


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


class UnsupportedMediaType(ClientError):
    code = 415
    message = 'The request entity is in a format that is not supported by this resource.'


class InternalServerError(ServerError):
    code = 500
    message = 'The server encountered an error while processing the request.'
