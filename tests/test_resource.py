from pytest import raises as assert_raises
from collections import defaultdict
from rhino.errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from rhino.mapper import Route
from rhino.request import Request
from rhino.resource import Resource, negotiate_content_type, negotiate_accept, \
        dispatch_request, make_response, request_handler
from rhino.response import Response
from rhino.urls import request_context


def make_request_handler(fn=None, verb=None, view=None, accepts='*/*', provides=None):
    return request_handler(fn=fn, verb=verb, view=view, accepts=accepts, provides=provides)


def test_negotiate_content_type():
    handlers = [
        make_request_handler(accepts='*/*'),
        make_request_handler(accepts='text/*'),
        make_request_handler(accepts='text/plain'),
        make_request_handler(accepts='text/plain'),
        make_request_handler(accepts='application/json'),
        make_request_handler(accepts='image/png;q=0.8'),
        make_request_handler(accepts='image/png;q=0.9'),
    ]
    assert negotiate_content_type('application/xml', handlers) == [handlers[0]]
    assert negotiate_content_type('text/html', handlers) == [handlers[1]]
    assert negotiate_content_type('text/plain', handlers) == handlers[2:4]
    assert negotiate_content_type('application/json', handlers) == [handlers[4]]
    assert negotiate_content_type('image/png', handlers) == [handlers[6]]


def test_negotiate_accept():
    handlers = [
        make_request_handler(provides='text/plain'),
        make_request_handler(provides='text/html'),
        make_request_handler(provides='application/json'),
    ]
    assert negotiate_accept('text/*', handlers) == [handlers[0]]
    assert negotiate_accept('text/plain;q=0.1, text/html', handlers) == [handlers[1]]
    assert negotiate_accept('text/*, application/json', handlers) == [handlers[2]]

    handlers = [
        make_request_handler(provides='text/plain'),
        make_request_handler(provides=None),
    ]
    assert negotiate_accept('text/*', handlers) == [handlers[1]]
    assert negotiate_accept('text/plain', handlers) == [handlers[1]]


def make_handler_dict():
    return defaultdict(lambda: defaultdict(list))


def add_handler(handler_dict, fn, verb, view=None, accepts='*/*', provides=None):
    handler = request_handler(fn, verb, view, accepts, provides)
    handler_dict[view][verb].append(handler)


def test_dispatch_request():
    assert_raises(NotFound, dispatch_request, Request({}), {})

    handler_dict = make_handler_dict()
    h = lambda req: 'ok'
    add_handler(handler_dict, h, 'GET',  provides='text/html')
    add_handler(handler_dict, h, 'POST', accepts='text/plain', provides='text/plain')
    add_handler(handler_dict, h, 'POST', accepts='text/plain', provides='image/png')

    res = dispatch_request(Request({'REQUEST_METHOD': 'GET'}), handler_dict)
    assert res.headers['Vary'] == 'Accept'
    assert res.headers['Content-Type'] == 'text/html'

    res = dispatch_request(Request({'REQUEST_METHOD': 'HEAD'}), handler_dict)
    assert res.headers['Vary'] == 'Accept'
    assert res.headers['Content-Type'] == 'text/html'

    res = dispatch_request(Request({'REQUEST_METHOD': 'OPTIONS'}), handler_dict)
    assert res.headers['Allow'] == 'GET, HEAD, OPTIONS, POST'

    assert_raises(MethodNotAllowed, dispatch_request, Request(
        {'REQUEST_METHOD': 'PUT'}), handler_dict)

    assert dispatch_request(Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/html'}), handler_dict)

    assert_raises(NotAcceptable, dispatch_request, Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/plain'}), handler_dict)

    assert_raises(NotAcceptable, dispatch_request, Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/plain'}), handler_dict)

    assert_raises(UnsupportedMediaType, dispatch_request, Request(
        {'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': 'text/html'}), handler_dict)

    res = dispatch_request(Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'text/plain'}), handler_dict)
    assert res.headers['Vary'] == 'Accept'
    assert res.headers['Content-Type'] == 'text/plain'

    res = dispatch_request(Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'image/png'}), handler_dict)
    assert res.headers['Vary'] == 'Accept'
    assert res.headers['Content-Type'] == 'image/png'

    assert_raises(NotAcceptable, dispatch_request, Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'application/json'}), handler_dict)


def test_make_response():
    assert_raises(TypeError, make_response, None)

    res = make_response('')
    assert res.code == 200
    assert res.body == ''

    orig = Response(200, body='test')
    res = make_response(orig)
    assert res is orig


def test_resource_dispatch_empty():
    r = Resource()
    req = Request({'REQUEST_METHOD': 'GET'})
    assert_raises(NotFound, r, req)
