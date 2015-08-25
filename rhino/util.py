from __future__ import absolute_import

import functools
import inspect

__all__ = [
    'apply_ctx',
    'sse_event',
]


def _sse_encode(k, v):
    # splitlines() discards the last trailing newline. Append an unambiguous
    # newline so that the presence or absence of a trailing newline in the
    # input string is preserved.
    v += '\r\n'
    # Normalize all newlines to \n. This happens anyway during reconstruction:
    # https://html.spec.whatwg.org/multipage/comms.html#event-stream-interpretation
    return ''.join('%s: %s\n' % (k, line) for line in v.splitlines())


# FIXME only comment and data may contain newlines!
def sse_event(event=None, data=None, id=None, retry=None, comment=None,
        encoding='utf-8'):
    """Encode a Server-Sent Event (SSE).

    At least one field must be present. All fields are strings, except retry,
    which must be an integer. The event and id fields can not contain newlines.
    """
    if all(x is None for x in [event, data, id, retry, comment]):
        raise TypeError("Event must have at least one field")
    if event and any(c in event for c in '\r\n'):
        raise ValueError("'event' can not contain newlines: '%s'" % event)
    if id and any(c in id for c in '\r\n'):
        raise ValueError("'id' can not contain newlines: '%s'" % id)
    return ''.join([
        _sse_encode('', comment) if comment is not None else '',
        _sse_encode('id', id) if id is not None else '',
        _sse_encode('event', event) if event is not None else '',
        _sse_encode('retry', str(int(retry))) if retry is not None else '',
        _sse_encode('data', data) if data is not None else '',
        '\n',
    ]).encode(encoding)


def dual_use_decorator(fn):
    """Turn a function into a decorator that can be called with or without
    arguments."""
    @functools.wraps(fn)
    def decorator(*args, **kw):
        if len(args) == 1 and not kw and callable(args[0]):
            return fn()(args[0])
        else:
            return fn(*args, **kw)
    return decorator


def dual_use_decorator_method(fn):
    """Turn a method into a decorator that can be called with or without
    arguments. """
    @functools.wraps(fn)
    def decorator(*args, **kw):
        if len(args) == 2 and not kw and callable(args[1]):
            return fn(args[0])(args[1])
        else:
            return fn(*args, **kw)
    return decorator


def get_args(obj):
    """Get a list of argument names for a callable."""
    if inspect.isfunction(obj):
        return inspect.getargspec(obj).args
    elif inspect.ismethod(obj):
        return inspect.getargspec(obj).args[1:]
    elif inspect.isclass(obj):
        return inspect.getargspec(obj.__init__).args[1:]
    elif hasattr(obj, '__call__'):
        return inspect.getargspec(obj.__call__).args[1:]
    else:
        raise TypeError("Can't inspect signature of '%s' object." % obj)


def apply_ctx(fn, ctx):
    """Return fn with ctx partially applied, if requested.

    If the `fn` callable accepts an argument named "ctx", returns a
    functools.partial object with ctx=ctx applied, else returns `fn` unchanged.

    For this to work, the 'ctx' argument must come after any arguments that are
    passed as positional arguments. For example, 'ctx' must be the 2nd argument
    for request handlers, serializers and deserializers, that are always called
    with one positional argument (the request, object to serialize, and input
    filehandle, respectively).
    """
    if 'ctx' in get_args(fn):
        return functools.partial(fn, ctx=ctx)
    else:
        return fn
