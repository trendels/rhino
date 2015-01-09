import json
from StringIO import StringIO

from rhino.mapper import Context
from rhino.request import Request
from rhino.resource import Resource, get, put
from rhino.errors import BadRequest

class json_repr(object):
    provides = 'application/json'
    accepts = 'application/json'

    @staticmethod
    def serialize(obj):
        return json.dumps(obj, sort_keys=True)

    @staticmethod
    def deserialize(f):
        return json.load(f)


class text_repr(object):
    provides = 'text/plain'
    accepts = 'text/plain'

    @staticmethod
    def serialize(obj):
        return '\n'.join(['%s=%s' % (k, v) for k, v in sorted(obj.items())])

    @staticmethod
    def deserialize(f):
        fields = {}
        for line in f:
            k, v = line.rstrip('\n').split('=', 1)
            fields[k] = v
        return fields


def test_produces():

    @get(produces=json_repr)
    @get(produces=text_repr)
    def get_data(request):
        return {'id': 1, 'name': 'fred'}

    r = Resource(get_data)
    response = r(Request({'HTTP_ACCEPT': 'application/json'}), Context())
    assert response.headers['Content-Type'] == 'application/json'
    assert response.body == '{"id": 1, "name": "fred"}'

    response = r(Request({'HTTP_ACCEPT': 'text/plain'}), Context())
    assert response.headers['Content-Type'] == 'text/plain'
    assert response.body == 'id=1\nname=fred'


def test_put_data():

    @put(consumes=json_repr)
    @put(consumes=text_repr)
    def put_data(request):
        return json.dumps(request.body, sort_keys=True)

    r = Resource(put_data)
    data = json.dumps({'id': 1, 'name': 'fred'})
    body = StringIO(data)

    response = r(Request({
        'REQUEST_METHOD': 'PUT',
        'CONTENT_TYPE': 'application/json',
        'CONTENT_LENGTH': str(len(data)),
        'wsgi.input': body,
    }), Context())
    assert response.body == '{"id": 1, "name": "fred"}'

    data = 'id=2\nname=barney'
    body = StringIO(data)

    response = r(Request({
        'REQUEST_METHOD': 'PUT',
        'CONTENT_TYPE': 'text/plain',
        'CONTENT_LENGTH': str(len(data)),
        'wsgi.input': body,
    }), Context())
    assert response.body == '{"id": "2", "name": "barney"}'
