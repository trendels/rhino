from rhino.test import TestClient

from examples.nested_mappers.main import app

client = TestClient(app.wsgi)

def test_redirect():
    status, headers, body = client.get('/')
    assert status == "302 Found"
    assert headers['Location'] == 'http://localhost/pages/'

def test_get_index():
    status, headers, body = client.get('/pages/')
    assert status == "200 OK"
    assert headers['Content-Type'] == 'text/html; charset=utf-8'
    assert '<h1>Welcome' in body
    assert '<a href="http://localhost/users/">' in body

def test_get_users():
    status, headers, body = client.get('/users/')
    assert '<h1>Users' in body
    assert '<a href="http://localhost/users/mia">' in body

def test_get_user():
    status, headers, body = client.get('/users/mia')
    assert '<h1>Mia' in body
    assert '<a href="http://localhost/">' in body
