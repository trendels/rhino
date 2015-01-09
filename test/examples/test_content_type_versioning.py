import json

from examples.content_type_versioning import app, \
        mime_type_v1, mime_type_v2, mime_type_v3

from rhino.test import TestClient

client = TestClient(app.wsgi)

def test_get_default():
    res = client.get('/')
    assert res.headers['Content-Type'] == mime_type_v3


def test_get_v1():
    res = client.get('/', accept=mime_type_v1)
    assert res.headers['Content-Type'] == mime_type_v1
    assert sorted(json.loads(res.body).keys()) == ['id', 'title']


def test_get_v2():
    res = client.get('/', accept=mime_type_v2)
    assert res.headers['Content-Type'] == mime_type_v2
    assert sorted(json.loads(res.body).keys()) == ['id', 'tags', 'title']


def test_get_v3():
    res = client.get('/', accept=mime_type_v3)
    assert res.headers['Content-Type'] == mime_type_v3
    assert sorted(json.loads(res.body).keys()) == [
            'date_published', 'id', 'tags', 'title']
