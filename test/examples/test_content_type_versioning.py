import json

from examples.content_type_versioning import app

from rhino.test import TestClient

client = TestClient(app.wsgi)

mime_type_v1 = 'application/vnd.acme.report+json;v=1'
mime_type_v2 = 'application/vnd.acme.report+json;v=2'
mime_type_v3 = 'application/vnd.acme.report+json;v=3'

def test_get_default():
    res = client.get('/')
    assert res.headers['Content-Type'] == mime_type_v3


def test_get_v1():
    res = client.get('/', accept=mime_type_v1)
    assert res.headers['Content-Type'] == mime_type_v1
    assert set(json.loads(res.body).keys()) == set(['title', 'author'])


def test_get_v2():
    res = client.get('/', accept=mime_type_v2)
    assert res.headers['Content-Type'] == mime_type_v2
    assert set(json.loads(res.body).keys()) == set(['title', 'author', 'date'])


def test_get_v3():
    res = client.get('/', accept=mime_type_v3)
    assert res.headers['Content-Type'] == mime_type_v3
    assert set(json.loads(res.body).keys()) == set(
            ['title', 'author', 'date', 'tags'])
