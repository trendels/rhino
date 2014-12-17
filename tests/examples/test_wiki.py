import os
import shutil
import tempfile

import pytest
from rhino.test import TestClient

from examples.wiki.wiki import app

@pytest.fixture
def client(request):
    tmpdir = tempfile.mkdtemp(prefix='rhino_test')
    cwd = os.getcwd()
    os.chdir(tmpdir)
    os.mkdir('contents')

    def finalize():
        os.chdir(cwd)
        shutil.rmtree(tmpdir)

    request.addfinalizer(finalize)
    return TestClient(app.wsgi)


def test_frontpage(client):
    status, headers, body = client.get('/')
    assert headers['Location'] == 'http://localhost/FrontPage'

    status, headers, body = client.get('/FrontPage')
    assert headers['Content-Type'] == 'text/html; charset=utf-8'
    assert 'FrontPage' in body


def test_edit(client):
    status, headers, body = client.get('/FrontPage/edit')
    assert 'Editing FrontPage' in body

    status, headers, body = client.post('/FrontPage/edit', {'content': 'xyz', 'submit': 1})
    assert status == "302 Found"
    assert headers['Location'] == 'http://localhost/FrontPage'

    status, headers, body = client.get('/FrontPage')
    assert 'xyz' in body


def test_history(client):
    client.post('/FrontPage/edit', {'content': 'test1', 'submit': 1})
    client.post('/FrontPage/edit', {'content': 'test2', 'submit': 1})

    status, headers, body = client.get('/FrontPage')
    assert 'test2' in body

    status, headers, body = client.get('/FrontPage/history')
    assert 'History For FrontPage' in body

    status, headers, body = client.post('/FrontPage/history', {'version': 1, 'submit': 1})
    assert status == "302 Found"
    assert headers['Location'] == 'http://localhost/FrontPage'

    status, headers, body = client.get('/FrontPage')
    assert 'test1' in body
