from collections import defaultdict

from pytest import raises as assert_raises
from rhino.errors import NotFound
from rhino.mapper import Context
from rhino.request import Request
from rhino.resource import Resource, get, put, delete
from rhino.response import Response, ok
from rhino.test import make_handler_metadata


def test_call():
    class TestResource(object):
        pass

    resource = TestResource()
    resource.fn1 = lambda r: Response(200, headers=[('Vary', 'User-Agent')], body='test')
    resource.fn1._rhino_meta = [make_handler_metadata(verb='GET', provides='text/plain')]
    resource.fn2 = lambda r: Response(200, body='test')
    resource.fn2._rhino_meta = [make_handler_metadata(verb='GET', provides='text/html')]
    resource.fn3 = lambda r: Response(200, body='test')
    resource.fn3._rhino_meta = [make_handler_metadata(verb='POST')]

    ctx = Context()
    wrapped = Resource(resource)

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
    r = Resource(None)
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = Context()
    assert_raises(NotFound, r, req, ctx)


def test_resource_fn():
    @get
    def handler1(request):
        return ok()

    @get
    def handler2(request, ctx):
        return ok()

    r1 = Resource(handler1)
    r2 = Resource(handler2)
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = Context()
    assert r1(req, ctx)
    assert r2(req, ctx)


def test_resource_obj():
    class MyResource(object):
        @get
        def handler1(self, request):
            return ok()

        @put
        def handler2(self, request, ctx):
            return ok()

    r = Resource(MyResource())
    ctx = Context()
    assert r(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert r(Request({'REQUEST_METHOD': 'PUT'}), ctx)


def test_resource_class():
    @Resource
    class MyResource(object):
        @get
        def handler1(self, request):
            return ok()

        @put
        def handler2(self, request, ctx):
            return ok()

    ctx = Context()
    assert MyResource(Request({'REQUEST_METHOD': 'GET'}), ctx)
    assert MyResource(Request({'REQUEST_METHOD': 'PUT'}), ctx)


def test_resource_from_url():
    class ResourceWithFromUrl(object):
        def __init__(self):
            self.called = False

        def from_url(self, request):
            self.called = True
            return {}

    class ResourceWithFromUrlCtx(ResourceWithFromUrl):
        def from_url(self, request, ctx):
            self.called = True
            return {}

    class ResourceWithFromUrlError(ResourceWithFromUrl):
        def from_url(self, request):
            self.called = True
            return 'test'

    resource1 = ResourceWithFromUrl()
    resource1.handler = get(lambda req: ok())

    resource2 = ResourceWithFromUrlCtx()
    resource2.handler = get(lambda req: ok())

    resource3 = ResourceWithFromUrlError()
    resource3.handler = get(lambda req: ok())

    r1 = Resource(resource1)
    r2 = Resource(resource2)
    r3 = Resource(resource3)
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = Context()
    assert r1(req, ctx)
    assert resource1.called
    assert r2(req, ctx)
    assert resource2.called
    assert_raises(TypeError, r3, req, ctx)
    assert resource3.called
