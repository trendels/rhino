import os
import shutil
import tempfile

import pytest
from rhino.test import TestClient

from examples.movie_db import model
from examples.movie_db.web import get_app


@pytest.fixture(scope='module')
def client(request):
    tmpdir = tempfile.mkdtemp(prefix='rhino_test')
    db_path = os.path.abspath(os.path.join(tmpdir, 'movies.db'))
    db_url = 'sqlite:///%s' % db_path
    model.init_db(db_url)

    def finalize():
        shutil.rmtree(tmpdir)

    request.addfinalizer(finalize)
    app = get_app(db_url)
    return TestClient(app.wsgi)


def test_index(client):
    res = client.get('/')
    assert res.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert "Movie Database" in res.body


def test_movie(client):
    res = client.get('/movies/1')
    assert "Star Wars" in res.body


def test_actor(client):
    res = client.get('/actors/1')
    assert "Mark Hamill" in res.body
