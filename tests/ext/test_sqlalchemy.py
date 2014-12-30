from rhino.mapper import Context
from rhino.ext.sqlalchemy import SessionProperty
from sqlalchemy.orm import Session


def test_default_engine():
    session_property = SessionProperty('sqlite:///:memory:')
    assert 'bind' in session_property.session_args
    assert session_property.session_args['bind'].name == 'sqlite'


def test_property():
    ctx = Context()
    ctx.add_property('session', SessionProperty('sqlite:///:memory:'))
    session = ctx.session
    assert isinstance(session, Session)
    assert ctx._Context__callbacks['teardown'][0] == session.close


def test_delay_close():
    ctx = Context()
    ctx.add_property('session',
            SessionProperty('sqlite:///:memory:', delay_close=True))
    session = ctx.session
    assert ctx._Context__callbacks['close'][0] == session.close
