from pytest import raises as assert_raises
from collections import defaultdict
from rhino.errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from rhino.mapper import Route
from rhino.request import Request
from rhino.resource import Resource, negotiate_content_type, negotiate_accept, \
        resolve_handler, make_response, request_handler
from rhino.response import Response
from rhino.test import make_request_handler


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


def test_make_response():
    assert_raises(TypeError, make_response, None)

    res = make_response('')
    assert res.code == 200
    assert res.body == ''

    orig = Response(200, body='test')
    res = make_response(orig)
    assert res is orig


def test_resource():
    resource = Resource()
    @resource.get
    def foo(): pass
    @resource.get('test')
    def bar(): pass

    assert resource.foo is foo
    assert resource.bar is bar

    assert resource.foo._rhino_meta.name == 'foo'
    assert resource.bar._rhino_meta.name == 'bar'
    assert resource.bar._rhino_meta.view == 'test'


def test_resource_url_for():
    resource1 = Resource()
    resource1.get(None)
    @resource1.from_url
    def from_url_1(request, ctx, positional, a, b):
        return {'x': 1, 'y': 2}

    resource2 = Resource()
    resource2.get(None)
    @resource2.from_url
    def from_url_2(request, positional, a, b):
        return {'x': 3, 'y': 4}

    req = Request({'REQUEST_METHOD': 'GET'})
    req.routing_args[0].append('arg')
    req.routing_args[1].update({'a': 1, 'b': 2})
    ctx = None
    assert resource1(req, ctx) is None
    assert req.routing_args == (['arg'], {'x': 1, 'y': 2})

    req = Request({'REQUEST_METHOD': 'GET'})
    req.routing_args[0].append('arg')
    req.routing_args[1].update({'a': 1, 'b': 2})
    ctx = None
    assert resource2(req, ctx) is None
    assert req.routing_args == (['arg'], {'x': 3, 'y': 4})
