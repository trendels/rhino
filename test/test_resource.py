from pytest import raises as assert_raises
from collections import defaultdict
from rhino.errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from rhino.mapper import Route, Context
from rhino.request import Request
from rhino.resource import Resource, negotiate_content_type, negotiate_accept, \
        resolve_handler, make_response, handler_metadata
from rhino.response import Response, ok
from rhino.test import make_handler_metadata


def test_negotiate_content_type():
    handlers = [
        make_handler_metadata(accepts='*/*'),
        make_handler_metadata(accepts='text/*'),
        make_handler_metadata(accepts='text/plain'),
        make_handler_metadata(accepts='text/plain'),
        make_handler_metadata(accepts='application/json'),
        make_handler_metadata(accepts='image/png;q=0.8'),
        make_handler_metadata(accepts='image/png;q=0.9'),
    ]
    assert negotiate_content_type('application/xml', handlers) == [handlers[0]]
    assert negotiate_content_type('text/html', handlers) == [handlers[1]]
    assert negotiate_content_type('text/plain', handlers) == handlers[2:4]
    assert negotiate_content_type('application/json', handlers) == [handlers[4]]
    assert negotiate_content_type('image/png', handlers) == [handlers[6]]


def test_negotiate_accept():
    handlers = [
        make_handler_metadata(provides='text/plain'),
        make_handler_metadata(provides='text/html'),
        make_handler_metadata(provides='application/json'),
    ]
    assert negotiate_accept('text/*', handlers) == [handlers[0]]
    assert negotiate_accept('text/plain;q=0.1, text/html', handlers) == [handlers[1]]
    assert negotiate_accept('text/*, application/json', handlers) == [handlers[2]]

    handlers = [
        make_handler_metadata(provides='text/plain'),
        make_handler_metadata(provides=None),
    ]
    assert negotiate_accept('text/*', handlers) == [handlers[1]]
    assert negotiate_accept('text/plain', handlers) == [handlers[1]]


def make_handler_dict():
    return defaultdict(lambda: defaultdict(list))


def add_handler(handler_dict, fn, verb, view=None, accepts='*/*', provides=None):
    handler = handler_metadata(fn, verb, view, accepts, provides)
    handler_dict[view][verb].append(handler)


def test_resolve_handler():
    assert_raises(NotFound, resolve_handler, Request({}), {})

    handlers = {
        None: {
            'GET': [
                make_handler_metadata(verb='GET', provides='text/html')
            ],
            'POST': [
                make_handler_metadata(verb='POST', accepts='text/plain', provides='text/plain'),
                make_handler_metadata(verb='POST', accepts='text/plain', provides='image/png'),
            ],
            'PUT': [
                make_handler_metadata(verb='PUT', accepts='text/plain'),
                make_handler_metadata(verb='PUT', accepts='application/json'),
            ],
        },
        'test': {
            'POST': [
                make_handler_metadata(verb='POST', accepts='text/plain', provides='text/plain'),
                make_handler_metadata(verb='POST', accepts='application/xml', provides='image/png'),
            ],
            'PUT': [
                make_handler_metadata(verb='PUT', accepts='text/plain'),
                make_handler_metadata(verb='PUT', accepts='*/*'),
            ]
        }
    }
    get_handlers = handlers[None]['GET']
    post_handlers = handlers[None]['POST']
    put_handlers = handlers[None]['PUT']
    post_handlers_test_view = handlers['test']['POST']
    put_handlers_test_view = handlers['test']['PUT']

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
    req._add_context(root=None, mapper=None, route=Route('/', None, name=':test'))
    rv = resolve_handler(req, handlers)
    assert rv == (post_handlers_test_view[1], vary_both)

    req = Request({'REQUEST_METHOD': 'PUT', 'CONTENT_TYPE': 'text/plain'})
    req._add_context(root=None, mapper=None, route=Route('/', None, name=':test'))
    rv = resolve_handler(req, handlers)
    assert rv == (put_handlers_test_view[0], vary_content_type)


def test_make_response():
    assert_raises(TypeError, make_response, None)

    res = make_response('')
    assert res.code == 200
    assert res.body == ''

    orig = Response(200, body='test')
    res = make_response(orig)
    assert res is orig


def test_resource_from_url():
    resource1 = Resource()

    @resource1.from_url
    def from_url_1(request, ctx, a, b):
        return {'x': 1, 'y': 2}

    @resource1.get
    def handler1(request, x, y):
        resource1.args = (x, y)
        return ok()

    resource2 = Resource()
    resource2.get(lambda req, x, y: ok())

    @resource2.from_url
    def from_url_2(request, a, b):
        return {'x': 3, 'y': 4}

    @resource2.get
    def handler2(request, x, y):
        resource2.args = (x, y)
        return ok()

    req = Request({'REQUEST_METHOD': 'GET'})
    req.routing_args.update({'a': 1, 'b': 2})
    ctx = Context()
    resource1(req, ctx)
    assert resource1.args == (1, 2)

    req = Request({'REQUEST_METHOD': 'GET'})
    req.routing_args.update({'a': 1, 'b': 2})
    ctx = Context()
    resource2(req, ctx)
    assert resource2.args == (3, 4)
