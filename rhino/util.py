from __future__ import absolute_import

import functools


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
