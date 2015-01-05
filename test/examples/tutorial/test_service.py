import json

import pytest
from rhino.test import TestClient

from examples.tutorial.service import app


@pytest.fixture
def client():
    return TestClient(app.wsgi)

def test_todo_list(client):
    response = client.get('/todos')
    assert response.code == 200
    assert response.headers.get('Content-Type') == 'text/plain'
    assert 'Profit!' in response.body

def test_todo_list_json(client):
    response = client.get('/todos', accept='application/json')
    assert response.code == 200
    assert response.headers.get('Content-Type') == 'application/json'
    todo_list = json.loads(response.body)
    assert todo_list[-1]['text'] == 'Profit!'
    assert todo_list[-1]['href'] == 'http://localhost/todos/3'

def test_todo_list_etag(client):
    response = client.get('/todos', accept='application/json')
    assert 'ETag' in response.headers
    etag = response.headers['ETag']
    response = client.get(
            '/todos', accept='application/json', if_none_match=etag)
    assert response.code == 304
    assert response.headers.get('ETag') == etag
    assert not response.body

