from examples.json_api import app

from rhino.test import TestClient

client = TestClient(app.wsgi)

def test_get():
    res = client.get('/')
    assert res.headers['Content-Type'] == 'application/json'
    assert res.body == '{"message": "hello, world!"}'


def test_put():
    res = client.put('/', '{"message": "hi"}', content_type='application/json')
    assert res.code == 200
    assert res.headers['Content-Type'] == 'application/json'
    assert res.body == '{"message": "hi"}'
