from __future__ import absolute_import

import functools
import inspect


def dual_use_decorator(fn):
    """
    Turn a function into a decorator that can be called with or without arguments.
    """
    @functools.wraps(fn)
    def decorator(*args, **kw):
        if len(args) == 1 and not kw and callable(args[0]):
            return fn()(args[0])
        else:
            return fn(*args, **kw)
    return decorator


def dual_use_decorator_method(fn):
    """
    Turn a method into a decorator that can be called with or without arguments.
    """
    @functools.wraps(fn)
    def decorator(*args, **kw):
        if len(args) == 2 and not kw and callable(args[1]):
            return fn(args[0])(args[1])
        else:
            return fn(*args, **kw)
    return decorator


def get_args(obj):
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
    if 'ctx' in get_args(fn):
        return fn(*args, ctx=ctx, **kw)
    else:
        return fn(*args, **kw)
