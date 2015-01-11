from StringIO import StringIO

from rhino.mapper import Context
from rhino.request import Request
from rhino.resource import Resource, get, put, post
from rhino.errors import BadRequest


class json_repr(object):
    provides = 'application/json'
    accepts = 'application/json'

    @staticmethod
    def serialize(obj):
        return 'json repr(%s)' % obj

    @staticmethod
    def deserialize(f):
        return 'json data(%s)' % f.read()


class text_repr(object):
    provides = 'text/plain'
    accepts = 'text/plain'
    @staticmethod
    def serialize(obj):
        return 'text repr(%s)' % obj

    @staticmethod
    def deserialize(f):
        return 'text data(%s)' % f.read()


def test_produces():

    @get(produces=json_repr)
    @get(produces=text_repr)
    def get_data(request):
        return 'ok'

    r = Resource(get_data)

    response = r(Request({'HTTP_ACCEPT': 'application/json'}), Context())
    assert response.headers['Content-Type'] == 'application/json'
    assert response.body == 'json repr(ok)'

    response = r(Request({'HTTP_ACCEPT': 'text/plain'}), Context())
    assert response.headers['Content-Type'] == 'text/plain'
    assert response.body == 'text repr(ok)'


def test_consumes():

    @put(consumes=json_repr)
    @put(consumes=text_repr)
    def put_data(request):
        return request.body

    r = Resource(put_data)

    response = r(Request({
        'REQUEST_METHOD': 'PUT',
        'CONTENT_TYPE': 'application/json',
        'CONTENT_LENGTH': '2',
        'wsgi.input': StringIO('ok'),
    }), Context())
    assert response.body == 'json data(ok)'

    response = r(Request({
        'REQUEST_METHOD': 'PUT',
        'CONTENT_TYPE': 'text/plain',
        'CONTENT_LENGTH': '2',
        'wsgi.input': StringIO('ok'),
    }), Context())
    assert response.body == 'text data(ok)'


def test_repr_context():

    class test_repr(text_repr):
        @staticmethod
        def serialize(obj, ctx):
            return 'serialize(%s, %s)' % (obj, id(ctx))

        @staticmethod
        def deserialize(f, ctx):
            return 'deserialize(%s, %s)' % (f.read(), id(ctx))

    @post(consumes=test_repr, produces=test_repr)
    def post_data(request):
        return request.body

    r = Resource(post_data)
    ctx = Context()

    response = r(Request({
        'REQUEST_METHOD': 'POST',
        'HTTP_ACCEPT': 'text/plain',
        'CONTENT_TYPE': 'text/plain',
        'CONTENT_LENGTH': '2',
        'wsgi.input': StringIO('ok'),
    }), ctx)
    assert response.body == 'serialize(deserialize(ok, %(id)s), %(id)s)' \
            % {'id': id(ctx)}
