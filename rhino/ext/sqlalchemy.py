"""
This module contains a SessionProperty class that can be used to add a
SQLALchemy Session object to the context.

This extension requires the SQLAlchemy module to be installed:

    $ pip install sqlalchemy

The session is closed at the end of every request. If you want the session to
be lazily initialized, use the `lazy` parameter of `Mapper.add_ctx_property`.

Example:

    app.add_ctx_property('db', SessionProperty(db_url), lazy=True)

Example usage:

    from rhino import Mapper, get
    from rhino.ext.sqlalchemy import SessionProperty

    from models import Movie  # module containing SQLAlchemy ORM classes

    app = rhino.Mapper()
    app.add_ctx_property('db', SessionProperty('sqlite:///db.sqlite'))

    @get
    def index(request, ctx):
        movies = ctx.db.query(Movie).all()
        # ...

    app.add('/', index)

"""
from __future__ import absolute_import

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

__all__ = [
    'SessionProperty',
]


class SessionProperty(object):
    # TODO add option to autocommit before close
    def __init__(self, url=None, delay_close=False, **session_args):
        if url is not None:
            session_args['bind'] = create_engine(url)
        self.session_args = session_args
        self.delay_close = delay_close

    def __call__(self, ctx):
        session = Session(**self.session_args)
        if self.delay_close:
            ctx.add_callback('close', session.close)
        else:
            ctx.add_callback('teardown', session.close)
        return session
