from pytest import raises as assert_raises
from collections import defaultdict
from rhino.errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from rhino.mapper import Route
from rhino.request import Request
from rhino.resource import Resource, negotiate_content_type, negotiate_accept, \
        resolve_handler, make_response, request_handler, dispatch_request
from rhino.response import Response


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


def test_resolve_handler():
    assert_raises(NotFound, resolve_handler, Request({}), {})

    handlers = {
        None: {
            'GET': [
                make_request_handler(verb='GET', provides='text/html')
            ],
            'POST': [
                make_request_handler(verb='POST', accepts='text/plain', provides='text/plain'),
                make_request_handler(verb='POST', accepts='text/plain', provides='image/png'),
            ],
            'PUT': [
                make_request_handler(verb='PUT', accepts='text/plain'),
                make_request_handler(verb='PUT', accepts='application/json'),
            ],
        },
        'test': {
            'POST': [
                make_request_handler(verb='POST', accepts='text/plain', provides='text/plain'),
                make_request_handler(verb='POST', accepts='application/xml', provides='image/png'),
            ],
        }
    }
    get_handlers = handlers[None]['GET']
    post_handlers = handlers[None]['POST']
    put_handlers = handlers[None]['PUT']
    post_handlers_test_view = handlers['test']['POST']
    no_vary = set()
    vary_accept = set(['Accept'])
    vary_content_type = set(['Content-Type'])
    vary_both = vary_accept | vary_content_type

    rv = resolve_handler(Request({'REQUEST_METHOD': 'GET'}), handlers)
    assert rv == (get_handlers[0], no_vary)

    rv = resolve_handler(Request({'REQUEST_METHOD': 'HEAD'}), handlers)
    assert rv == (get_handlers[0], no_vary)

    rv = resolve_handler(Request({'REQUEST_METHOD': 'OPTIONS'}), handlers)
    assert rv[0].verb == 'OPTIONS'
    assert rv[1] == set()

    assert_raises(MethodNotAllowed, resolve_handler, Request(
        {'REQUEST_METHOD': 'DELETE'}), handlers)

    rv = resolve_handler(Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/html'}), handlers)
    assert rv == (get_handlers[0], no_vary)

    assert_raises(NotAcceptable, resolve_handler, Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/plain'}), handlers)

    assert_raises(NotAcceptable, resolve_handler, Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/plain'}), handlers)

    assert_raises(UnsupportedMediaType, resolve_handler, Request(
        {'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': 'text/html'}), handlers)

    rv = resolve_handler(Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'text/plain'}), handlers)
    assert rv == (post_handlers[0], vary_accept)

    rv = resolve_handler(Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'image/png'}), handlers)
    assert rv == (post_handlers[1], vary_accept)

    assert_raises(NotAcceptable, resolve_handler, Request(
        {'REQUEST_METHOD': 'POST',
         'CONTENT_TYPE': 'text/plain',
         'HTTP_ACCEPT': 'application/json'}), handlers)

    rv = resolve_handler(Request(
        {'REQUEST_METHOD': 'PUT',
         'CONTENT_TYPE': 'application/json'}), handlers)
    assert rv == (put_handlers[1], vary_content_type)

    req = Request({'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': 'application/xml'})
    req._add_context(root=None, mapper=None, route=Route('/', None, view='test'))
    rv = resolve_handler(req, handlers)
    assert rv == (post_handlers_test_view[1], vary_both)


def test_dispatch_request():
    fn1 = lambda r, c: Response(200, headers=[('Vary', 'User-Agent')], body='test')
    fn2 = lambda r, c: Response(200, body='test')
    handlers = {
        None: {
            'GET': [
                make_request_handler(fn1, verb='GET', provides='text/plain'),
                make_request_handler(fn2, verb='GET', provides='text/html'),
            ],
            'POST': [
                make_request_handler(fn2, verb='POST')
            ],
        },
    }
    ctx = None
    routing_args = ([], {})

    res = dispatch_request(Request({'REQUEST_METHOD': 'GET'}), ctx,
            handlers, routing_args)
    assert res.headers['Content-Type'] == 'text/plain'
    assert res.headers['Vary'] == 'Accept, User-Agent'

    res = dispatch_request(Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/html'}), ctx,
        handlers, routing_args)
    assert res.headers['Content-Type'] == 'text/html'
    assert res.headers['Vary'] == 'Accept'

    res = dispatch_request(Request(
        {'REQUEST_METHOD': 'POST', 'HTTP_ACCEPT': 'text/html'}), ctx,
        handlers, routing_args)
    assert 'Content-Type' not in res.headers
    assert 'Vary' not in res.headers


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
    ctx = None
    assert_raises(NotFound, r, req, ctx)
