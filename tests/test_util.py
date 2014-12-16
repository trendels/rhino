import functools

from rhino.util import dual_use_decorator, dual_use_decorator_method


@dual_use_decorator
def decorator_function(*args, **kw):
    """decorator function"""
    decorator_args = (args, kw)
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kw):
            return {'func_args': (args, kw),
                    'decorator_args': decorator_args}
        return wrapper
    return decorator


class MyClass(object):
    @dual_use_decorator_method
    def decorator_method(self, *args, **kw):
        """decorator method"""
        decorator_args = (args, kw)
        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kw):
                return {'func_args': (args, kw),
                        'decorator_args': decorator_args}
            return wrapper
        return decorator


def test_docstrings():
    assert decorator_function.__doc__ == 'decorator function'
    assert MyClass.decorator_method.__doc__ == 'decorator method'


def test_dual_use_decorator():
    @decorator_function
    def foo():
        """foo function"""
        pass

    assert foo(1, a=2) == {
        'func_args': ((1,), {'a': 2}),
        'decorator_args': (tuple(), {}),
    }
    assert foo.__doc__ == 'foo function'


def test_dual_use_decorator_with_args():
    @decorator_function(3, b=4)
    def foo():
        """foo function"""
        pass

    assert foo(1, a=2) == {
        'func_args': ((1,), {'a': 2}),
        'decorator_args': ((3,), {'b': 4}),
    }
    assert foo.__doc__ == 'foo function'


def test_dual_use_decorator_method():
    obj = MyClass()
    @obj.decorator_method
    def foo():
        """foo function"""
        pass

    assert foo(1, a=2) == {
        'func_args': ((1,), {'a': 2}),
        'decorator_args': (tuple(), {}),
    }
    assert foo.__doc__ == 'foo function'


def test_dual_use_decorator_method_with_args():
    obj = MyClass()
    @obj.decorator_method(3, b=4)
    def foo():
        """foo function"""
        pass

    assert foo(1, a=2) == {
        'func_args': ((1,), {'a': 2}),
        'decorator_args': ((3,), {'b': 4}),
    }
    assert foo.__doc__ == 'foo function'
