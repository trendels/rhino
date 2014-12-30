from rhino.test import TestClient

from examples.helloworld import app

client = TestClient(app.wsgi)


def test_get():
    res = client.get('/')
    assert res.code == 200
    assert res.headers.items() == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '13'),
    ]
    assert res.body == 'Hello, world!'


def test_head():
    res = client.head('/')
    assert res.code == 200
    assert res.headers.items() == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '13'),
    ]
    assert res.body == ''


def test_options():
    res = client.options('/')
    assert res.code == 200
    assert res.headers['Allow'] == 'GET, HEAD, OPTIONS'


def test_delete():
    res = client.delete('/')
    assert res.code == 405
    assert res.headers['Allow'] == 'GET, HEAD, OPTIONS'
