from pytest import raises as assert_raises
from rhino.errors import NotFound
from rhino.request import Request
from rhino.resource import ResourceWrapper, Resource
from rhino.response import Response
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


def test_dispatch_empty():
    r = ResourceWrapper(Resource())
    req = Request({'REQUEST_METHOD': 'GET'})
    ctx = None
    assert_raises(NotFound, r, req, ctx)
