"""
This module contains classes that can be used to add session support for Rhino
applications.

This extension requires the Beaker module to be installed::

    $ pip install beaker

The Session class provides a simple and easy to use signed cookie-based session
with support for displaying "flashed" messages.

The BeakerSession class provides access to the different backends provided by
beaker.session.
"""
from __future__ import absolute_import

from collections import namedtuple
from functools import partial

import beaker.session
from beaker.util import coerce_session_params

__all__ = [
    'BeakerSession',
    'Session',
    'SessionObject',
]

message = namedtuple('message', 'type text')


class SessionObject(beaker.session.SessionObject):
    """A session object with support for "flashed" messages."""

    _msg_key = '_msg'

    def add_message(self, text, type=None):
        """Add a message with an optional type."""
        key = self._msg_key
        self.setdefault(key, [])
        self[key].append(message(type, text))
        self.save()

    def pop_messages(self, type=None):
        """Retrieve stored messages and remove them from the session.

        Return all messages with a specific type, or all messages when `type`
        is None. Messages are returned in the order they were added. All
        messages returned in this way are removed from the session and will not
        be returned in subsequent calls.

        Returns a list of namedtuples with the fields (type, text).
        """
        key = self._msg_key
        messages = []
        if type is None:
            messages = self.pop(key, [])
        else:
            keep_messages = []
            for msg in self.get(key, []):
                if msg.type == type:
                    messages.append(msg)
                else:
                    keep_messages.append(msg)
            if not keep_messages and key in self:
                del self[key]
            else:
                self[key] = keep_messages
        if messages:
            self.save()

        return messages


class BeakerSession(object):
    """Adds a session property to the context."""
    session_class = SessionObject

    def __init__(self, **session_args):
        # Default parameters from beaker.middleware.SessionMiddleware
        self.options = dict(invalidate_corrupt=True, type=None,
                            data_dir=None, key='beaker.session.id',
                            timeout=None, secret=None, log_file=None)
        self.options.update(session_args)
        coerce_session_params(self.options)

    def finalize(self, session, request, response):
        if session.accessed():
            session.persist()
            if session.__dict__['_headers']['set_cookie']:
                cookie = session.__dict__['_headers']['cookie_out']
                if cookie:
                    response.headers.add_header('Set-Cookie', cookie)

    # TODO Since context properties are lazily initialized by default, the
    # session will not be loaded at all unless it is accessed at least once
    # during the request.
    def __call__(self, ctx):
        session = self.session_class(ctx.request.environ, **self.options)
        ctx.add_callback('finalize', partial(self.finalize, session))
        return session


class Session(BeakerSession):
    """Adds a session based on signed cookies to the context."""
    session_class = SessionObject

    # Avoid passing **kwargs to Beaker because it silently ignores unknown
    # arguments -- bad when you have a typo (e.g. htponly vs httponly).
    def __init__(
            self, secret, timeout=None, cookie_name='session_id',
            cookie_expires=True, cookie_domain=None, cookie_path='/',
            secure=False, httponly=False, auto=True):
        super(Session, self).__init__(
            type='cookie',
            validate_key=secret,
            key=cookie_name,
            timeout=timeout,
            cookie_expires=cookie_expires,
            cookie_domain=cookie_domain,
            cookie_path=cookie_path,
            secure=secure,
            httponly=httponly,
            auto=auto,
        )
