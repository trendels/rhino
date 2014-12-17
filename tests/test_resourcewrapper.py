from collections import defaultdict

from pytest import raises as assert_raises
from rhino.errors import NotFound
from rhino.request import Request
from rhino.resource import ResourceWrapper, Resource, get, put, delete
from rhino.response import Response, ok
from rhino.test import make_request_handler


def test_call():
    class TestResource(object):
        pass

    resource = TestResource()
    resource.fn1 = lambda r: Response(200, headers=[('Vary', 'User-Agent')], body='test')
    resource.fn1._rhino_meta = make_request_handler(None, verb='GET', provides='text/plain')
    resource.fn2 = lambda r: Response(200, body='test')
    resource.fn2._rhino_meta = make_request_handler(None, verb='GET', provides='text/html')
    resource.fn3 = lambda r: Response(200, body='test')
    resource.fn3._rhino_meta = make_request_handler(None, verb='POST')

    ctx = None
    wrapped = ResourceWrapper(resource)

    res = wrapped(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert res.headers['Content-Type'] == 'text/plain'
    assert res.headers['Vary'] == 'Accept, User-Agent'

    res = wrapped(Request(
        {'REQUEST_METHOD': 'GET', 'HTTP_ACCEPT': 'text/html'}), ctx)
    assert res.headers['Content-Type'] == 'text/html'
    assert res.headers['Vary'] == 'Accept'

    res = wrapped(Request(
        {'REQUEST_METHOD': 'POST', 'HTTP_ACCEPT': 'text/html'}), ctx)
    assert 'Content-Type' not in res.headers
    assert 'Vary' not in res.headers


def test_resource_emtpy():
    r = ResourceWrapper(None)
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = None
    assert_raises(NotFound, r, req, ctx)


def test_resource_fn():
    r1 = ResourceWrapper(lambda req: ok())
    r2 = ResourceWrapper(lambda req, ctx: ok())
    r3 = ResourceWrapper(lambda req: None)
    r4 = ResourceWrapper(lambda req: 'test')
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = None
    assert r1(req, ctx)
    assert r2(req, ctx)
    assert_raises(NotFound, r3, req, ctx)
    assert_raises(TypeError, r4, req, ctx)


def test_resource_obj():
    class Resource(object):
        @get
        def handler1(self, request):
            return ok()

        @put
        def handler2(self, request, ctx):
            return ok()

    resource = Resource()
    resource.handler3 = delete(lambda req: ok())

    r = ResourceWrapper(resource)
    ctx = None
    assert r(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert r(Request({'REQUEST_METHOD': 'PUT'}), ctx)
    assert r(Request({'REQUEST_METHOD': 'DELETE'}), ctx)


def test_resource_obj_call():
    class ResourceWithCall(object):
        def __init__(self):
            self.called = False

        def __call__(self, request):
            self.called = True

    class ResourceWithCallCtx(ResourceWithCall):
        def __call__(self, request, ctx):
            self.called = True

    class ResourceWithCallError(ResourceWithCall):
        def __call__(self, request):
            self.called = True
            return 'test'

    resource1 = ResourceWithCall()
    resource1.handler = get(lambda req: ok())

    resource2 = ResourceWithCallCtx()
    resource2.handler = get(lambda req: ok())

    resource3 = ResourceWithCallError()
    resource3.handler = get(lambda req: ok())

    r1 = ResourceWrapper(resource1)
    r2 = ResourceWrapper(resource2)
    r3 = ResourceWrapper(resource3)
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = None
    assert r1(req, ctx)
    assert resource1.called
    assert r2(req, ctx)
    assert resource2.called
    assert_raises(ValueError, r3, req, ctx)
    assert resource3.called


def test_resource_class():
    calls = defaultdict(list)

    class Resource(object):
        def __init__(self):
            calls[self.__class__].append('__init__')

        @get
        def handler(self, request):
            return ok()

    class ResourceWithCall(Resource):
        def __call__(self, request):
            calls[self.__class__].append('__call__')

    r1 = ResourceWrapper(Resource)
    r2 = ResourceWrapper(ResourceWithCall)
    ctx = None
    assert r1(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert calls[Resource] == ['__init__']
    assert r2(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert calls[ResourceWithCall] == ['__init__', '__call__']
