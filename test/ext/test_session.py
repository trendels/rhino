from pytest import raises as assert_raises
from rhino import Mapper, get
from rhino.ext.session import CookieSession, SessionObject, message, \
        SessionError
from rhino.test import TestClient


def test_messages():
    session = SessionObject(environ={})
    session.add_message('test')
    assert session.pop_messages() == [message(None, 'test')]
    assert session.pop_messages() == []


def test_pop_all_messages():
    session = SessionObject(environ={})
    session.add_message('test')
    session.add_message('test', type='foo')
    session.add_message('test', type='bar')
    assert session.pop_messages() == [
        message(None, 'test'),
        message('foo', 'test'),
        message('bar', 'test'),
    ]
    assert session.pop_messages() == []


def test_messages_by_type():
    session = SessionObject(environ={})
    session.add_message('test')
    session.add_message('test', type='foo')
    session.add_message('test', type='bar')
    assert session.pop_messages('foo') == [message('foo', 'test')]
    assert session.pop_messages('bar') == [message('bar', 'test')]
    assert session.pop_messages() == [message(None, 'test')]
    assert session.pop_messages('foo') == []
    assert session.pop_messages('bar') == []


def test_secret_required():
    assert_raises(SessionError, CookieSession, None)
    assert CookieSession(secret='foo')


def test_session_property():
    @get
    def handler(request, ctx):
        ctx.session['foo'] = 'bar'
        return 'test'

    app = Mapper()
    app.add_ctx_property('session', CookieSession(secret='test'))
    app.add('/', handler)
    client = TestClient(app.wsgi)

    res = client.get('/')
    assert 'session_id' in res.headers['Set-Cookie']
