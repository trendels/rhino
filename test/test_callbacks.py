from functools import partial

import mock
from mock import call
from pytest import raises as assert_raises

from rhino.errors import NotFound
from rhino.mapper import Mapper
from rhino.resource import Resource, get
from rhino.response import ok
from rhino.test import TestClient

class CallbackError(Exception): pass


class Wrapper(object):
    def __init__(self, wrapped, exceptions=None):
        self.wrapped = wrapped
        self.request = None
        self.response = None
        self.exceptions = exceptions or []
        self.cb = mock.create_autospec(lambda *args, **kw: 1)

    def error(self, msg, *args, **kw):
        raise CallbackError(msg)

    def __call__(self, request, ctx):
        self.request = request
        for cb_phase in ('enter leave finalize teardown close'.split()):
            if cb_phase in self.exceptions:
                ctx.add_callback(cb_phase, partial(self.cb, cb_phase + '-pre'))
                ctx.add_callback(cb_phase, partial(self.error, cb_phase))
                ctx.add_callback(cb_phase, partial(self.cb, cb_phase + '-post'))
            else:
                ctx.add_callback(cb_phase, partial(self.cb, cb_phase))
        self.response = self.wrapped(request, ctx)
        return self.response


def test_callbacks():
    @get
    def handler(request):
        return ok('test')

    wrapper = Wrapper(Resource(handler))

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    res = client.get('/')
    assert res.code == 200

    wrapper.cb.assert_has_calls([
        call('enter', wrapper.request),
        call('leave', wrapper.request, wrapper.response),
        call('finalize', wrapper.request, wrapper.response),
        call('teardown'),
        call('close'),
    ])


def test_callbacks_exception():
    not_found = NotFound()

    @get
    def handler(request):
        raise not_found

    wrapper = Wrapper(Resource(handler))

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    res = client.get('/')
    assert res.code == 404

    wrapper.cb.assert_has_calls([
        call('enter', wrapper.request),
        call('teardown'),
        call('close'),
    ])


def test_teardown_callbacks_swallow_exceptions():
    @get
    def handler(request):
        return ok('test')

    wrapper = Wrapper(Resource(handler), exceptions=('teardown,'))

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    res = client.get('/')
    assert res.code == 200

    wrapper.cb.assert_has_calls([
        call('enter', wrapper.request),
        call('leave', wrapper.request, wrapper.response),
        call('finalize', wrapper.request, wrapper.response),
        call('teardown-pre'),
        call('teardown-post'),
        call('close'),
    ])


def test_teardown_callbacks_run_after_wsgi_response_error():
    @get
    def handler(request):
        return 1  # Not a valid response

    wrapper = Wrapper(Resource(handler))

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    assert_raises(TypeError, client.get, '/')

    wrapper.cb.assert_has_calls([
        call('enter', wrapper.request),
        call('leave', wrapper.request, wrapper.response),
        call('finalize', wrapper.request, wrapper.response),
        call('teardown'),
    ])


def test_finalize_callbacks_before_conditional_response():
    def finalize_cb(req, res):
        res.headers.add('ETag', '"1"')

    @get
    def handler(request, ctx):
        ctx.add_callback('finalize', finalize_cb)
        return ok('test')

    app = Mapper()
    app.add('/', handler)

    client = TestClient(app.wsgi)
    res = client.get('/', if_none_match='"1"')
    assert res.code == 304
