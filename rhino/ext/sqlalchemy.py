from __future__ import absolute_import

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class SessionProperty(object):
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
