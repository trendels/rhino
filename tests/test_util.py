import functools

from pytest import raises as assert_raises

from rhino.util import dual_use_decorator, dual_use_decorator_method, get_args


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


def test_get_args():
    class Foo(object):
        def __init__(self, a, b):
            pass

        def __call__(self, e, f):
            pass

        def foo(self, g, h):
            pass

        @classmethod
        def bar(cls, i, j):
            pass

        @staticmethod
        def baz(k, l):
            pass

    foo = Foo(None, None)

    assert get_args(lambda x: None) == ['x']

    assert get_args(Foo) == ['a', 'b']
    assert get_args(Foo.foo) == ['g', 'h']
    assert get_args(Foo.bar) == ['i', 'j']
    assert get_args(Foo.baz) == ['k', 'l']

    assert get_args(foo) == ['e', 'f']
    assert get_args(foo.foo) == ['g', 'h']
    assert get_args(foo.bar) == ['i', 'j']
    assert get_args(foo.baz) == ['k', 'l']

    assert_raises(TypeError, get_args, None)
