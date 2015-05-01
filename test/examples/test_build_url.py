from rhino.test import TestClient

from examples.build_url import app

client = TestClient(app.wsgi)


def test_index():
    res = client.get('/')
    assert res.code == 302
    assert res.headers['Location'] == 'http://localhost/u:1/p:1'

def test_url():
    res = client.get('/u:1/p:1')
    assert 'http://localhost/u:1/p:1' in res.body
