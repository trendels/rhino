from rhino.mapper import Mapper, Context
from rhino.request import Request
from rhino.response import Response


class Wrapper(object):
    response = Response(200)

    def __init__(self, app):
        self._wrapped = app
        self.called = False

    def __call__(self, request, ctx):
        self.request = request
        self.ctx = ctx
        self.called = True
        return self.response

class Wrapper2(Wrapper):
    response = Response(204)

    def __call__(self, request, ctx):
        self.request = request
        self.ctx = ctx
        self.called = True
        return self._wrapped(request, ctx)


def test_wrapper():
    app = Mapper()
    app.add_wrapper(Wrapper)
    req = Request({})
    ctx = Context()
    res = app(req, ctx)

    wrapper = app._wrapped
    assert wrapper.called
    assert wrapper.request is req
    assert wrapper.ctx is ctx
    assert res is wrapper.response


def test_wrapper_nested():
    app = Mapper()
    app.add_wrapper(Wrapper)
    app.add_wrapper(Wrapper2)
    req = Request({})
    ctx = Context()
    res = app(req, ctx)

    outer = app._wrapped
    inner = outer._wrapped
    assert isinstance(outer, Wrapper2)
    assert isinstance(inner, Wrapper)

    assert outer.called
    assert outer.request is req
    assert outer.ctx is ctx

    assert inner.called
    assert inner.request is req
    assert inner.ctx is ctx

    assert res is inner.response
