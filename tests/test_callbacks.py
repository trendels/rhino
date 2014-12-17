from functools import partial

from mock import Mock, call

from rhino.errors import NotFound
from rhino.mapper import Mapper
from rhino.resource import get
from rhino.test import TestClient


class Wrapper(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.request = None
        self.response = None
        self.cb = Mock()

    def __call__(self, request):
        self.request = request
        request.add_callback('enter', partial(self.cb, 'enter'))
        request.add_callback('leave', partial(self.cb, 'leave'))
        request.add_callback('finalize', partial(self.cb, 'finalize'))
        request.add_callback('teardown', partial(self.cb, 'teardown'))
        request.add_callback('close', partial(self.cb, 'close'))
        self.response = self.wrapped(request)
        return self.response


def test_callbacks():

    @get
    def handler(request):
        return 'test'

    wrapper = Wrapper(handler)

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    res = client.get('/')
    assert res.code == 200

    assert wrapper.cb.mock_calls == [
        call('enter', wrapper.request),
        call('leave', wrapper.request, wrapper.response),
        call('finalize', wrapper.request, wrapper.response),
        call('teardown'),
        call('close'),
    ]


def test_callbacks_exception():
    not_found = NotFound()

    @get
    def handler(request):
        raise not_found

    wrapper = Wrapper(handler)

    app = Mapper()
    app.add('/', wrapper)

    client = TestClient(app.wsgi)
    res = client.get('/')
    assert res.code == 404

    assert wrapper.cb.mock_calls == [
        call('enter', wrapper.request),
        call('finalize', wrapper.request, not_found.response),
        call('teardown'),
        call('close'),
    ]
