"""
This extension requires the Beaker module to be installed::

    $ pip install beaker
"""
from __future__ import absolute_import

from collections import namedtuple
from functools import partial

import beaker.session
from beaker.util import coerce_session_params

message = namedtuple('message', 'type text')


class SessionObject(beaker.session.SessionObject):
    """
    A subclass of beaker.session.SessionObject with support for
    "flashed" messages.
    """

    #: The key name to use for storing messages in the session dict.
    _msg_key = '_msg'

    def add_message(self, text, type=None):
        """Add a message."""
        key = self._msg_key
        self.setdefault(key, [])
        self[key].append(message(type, text))
        self.save()

    def pop_messages(self, type=None):
        """Get all of a specific type. When type is None, returns all messages.
        Messages are returned as namedtuples with fields "type" and
        "text". Messages returned by this function are removed from
        the session.
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
    """Support for beaker.session

    Usage::

        app = rhino.Mapper()
        app.add_ctx_property('session', BeakerSession(**config))

    In a request handler, the session can now be accessed as ``ctx.session``.
    """

    session_class = beaker.session.SessionObject

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
    """A simple Session based on signed cookies with support for "flashed"
    messages.

    Usage::

        app = rhino.Mapper()
        app.add_ctx_property('session', Session(secret='...'))

    In a request handler, the session can now be accessed as ``ctx.session``.

    The session object has two methods to support "flashed" messages. The
    ``add_message`` method accepts a message text and optional message type
    (a string)::

        session.add_message('Welcome!')
        session.add_message('And error occured', type='error')

    The ``pop_messages`` method retrieves all messages, or all messages
    of a particular type, if used with the ``type`` argument (type=None means
    all messages). It return a list of messages as dictionaries with the keys
    ``'text'`` (the message text), and ``'type'`` (the message type).

    For example, in a template you could write::

        {% for msg in ctx.pop_messages() %}
          <div class="message {% msg.type %}">{% msg.text %}</div>
        {% endfor %}

    to show all messages, or::

        <p>Errors:</p>
        {% for msg in ctx.pop_messages(type='error') %}
          <div class="error">{% msg.text %}</div>
        {% endfor %}

    to show only messages of type "error".

    Messages returned by ``pop_messages`` will be removed from the session
    and not returned again.
    """

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
