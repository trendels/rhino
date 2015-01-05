from rhino.test import TestClient

from examples.conneg import app

client = TestClient(app.wsgi)


def test_get_html():
    res = client.get('/', accept='text/html')
    assert res.code == 200
    assert res.headers['Content-Type'] == 'text/html'
    assert res.body == '<html><h1>Hello, world!</h1></html>'


def test_get_json():
    res = client.get('/', accept='application/json')
    assert res.code == 200
    assert res.headers['Content-Type'] == 'application/json'
    assert res.body == '{"greeting": "Hello, world!"}'

def test_put_json():
    res = client.put('/', '{"greeting": "Howdy!"}', content_type='application/json')
    assert res.code == 200

    res = client.get('/', accept='application/json')
    assert res.body == '{"greeting": "Howdy!"}'
