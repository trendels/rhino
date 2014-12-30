import os
import shutil
import tempfile

import pytest
from pytest import raises as assert_raises
from rhino.mapper import Mapper
from rhino.static import StaticFile, StaticDirectory
from rhino.test import TestClient


@pytest.fixture(scope='module')
def tmpdir(request):
    tmpdir = tempfile.mkdtemp(prefix='rhino_test')
    request.addfinalizer(lambda: shutil.rmtree(tmpdir))
    return tmpdir


@pytest.fixture(scope='module')
def app(tmpdir):
    robots_txt = os.path.join(tmpdir, 'robots.txt')
    with open(robots_txt, 'w') as f:
        f.write('robots.txt')

    index_html = os.path.join(tmpdir, 'index.html')
    with open(index_html, 'w') as f:
        f.write('index.html')

    binary_file = os.path.join(tmpdir, 'file')
    with open(binary_file, 'w') as f:
        f.write('\0')

    app = Mapper()
    app.add('/robots.txt', StaticFile(robots_txt, expires=60), 'robots')
    app.add('/somefile.bin', StaticFile(binary_file), 'binary')
    app.add('/static/{path:any}', StaticDirectory(tmpdir, expires=120), 'static')
    return app


@pytest.fixture
def client(app):
    client = TestClient(app.wsgi)
    return client


def test_add_invalid_file():
    assert_raises(ValueError, StaticFile, 'file.does.not.exist')


def test_plain(client):
    res = client.get('/robots.txt')
    assert res.status == "200 OK"
    assert res.body == "robots.txt"
    assert res.headers['Content-Type'] == "text/plain"
    assert res.headers['Content-Length'] == "10"
    assert 'Expires' in res.headers

    res = client.post('/robots.txt', {})
    assert res.status == "405 Method Not Allowed"
    assert res.headers['Allow'] == 'GET, HEAD'


def test_binary(client):
    res = client.get('/somefile.bin')
    assert res.status == "200 OK"
    assert res.body == '\0'
    assert res.headers['Content-Type'] == "application/octet-stream"
    assert res.headers['Content-Length'] == "1"

    res = client.post('/robots.txt', {})
    assert res.status == "405 Method Not Allowed"
    assert res.headers['Allow'] == 'GET, HEAD'


def test_static_dir(client):
    res = client.get('/static/index.html')
    assert res.status == "200 OK"
    assert res.body == "index.html"
    assert res.headers['Content-Type'] == "text/html"
    assert res.headers['Content-Length'] == "10"
    assert 'Expires' in res.headers

    res = client.get('/static/')
    assert res.status == "404 Not Found"
    assert 'Expires' not in res.headers

    res = client.get('/static/does_not_exist')
    assert res.status == "404 Not Found"


def test_no_pathname_leak(client, tmpdir):
    res = client.get('/static/index.html')
    assert res.status == "200 OK"

    dirname = os.path.basename(tmpdir)
    res = client.get('/static/../%s/index.html' % dirname)
    assert res.status == "404 Not Found"
    res = client.get('/static/foo/../../%s/index.html' % dirname)
    assert res.status == "404 Not Found"
