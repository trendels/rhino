from __future__ import absolute_import

import functools
import inspect

__all__ = [
    'call_with_ctx',
    'sse_event',
]


def _sse_encode(k, v):
    return ''.join('%s: %s\n' % (k, line) for line in v.split('\n'))


def sse_event(event=None, data=None, id=None, retry=None, comment=None,
        encoding='utf-8'):
    """Encode a Server-Sent Event (SSE).

    At least one field must be present. All fields are strings, except
    retry, which should be an integer. The data and comment fields can contain
    newlines.
    """
    if all(x is None for x in [event, data, id, retry, comment]):
        raise TypeError("Event must have at least one field")
    return ''.join([
        _sse_encode('', comment) if comment is not None else '',
        _sse_encode('id', id) if id is not None else '',
        _sse_encode('event', event) if event is not None else '',
        _sse_encode('retry', str(retry)) if retry is not None else '',
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


def call_with_ctx(fn, ctx, *args, **kw):
    """Call fn with or without 'ctx', depending on its signature.

    If the `fn` callable accepts an argument named "ctx", then `ctx` will be
    passed as a keyword argument, else it will be ignored.
    """
    if 'ctx' in get_args(fn):
        return fn(*args, ctx=ctx, **kw)
    else:
        return fn(*args, **kw)
