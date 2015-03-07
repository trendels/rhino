from mock import Mock, call
from pytest import raises as assert_raises
from rhino.mapper import Context, Mapper, InvalidArgumentError
from rhino.request import Request
from rhino.response import ok
from rhino.test import assert_mock_has_no_calls


def test_add_property():
    foo = Mock(return_value=1)
    ctx = Context()
    ctx.add_property('foo', foo)
    foo.assert_called_once_with(ctx)
    assert ctx.foo == 1
    assert ctx.foo == 1
    foo.assert_called_once_with(ctx)


def test_add_property_lazy():
    foo = Mock(return_value=1)
    ctx = Context()
    ctx.add_property('foo', foo, lazy=True)
    assert_mock_has_no_calls(foo)
    assert ctx.foo == 1
    assert ctx.foo == 1
    foo.assert_called_once_with(ctx)


def test_invalid_property():
    ctx = Context()
    assert_raises(AttributeError, lambda: ctx.foo)


def test_add_property_duplicate():
    ctx = Context()
    ctx.add_property('foo', 1)
    assert_raises(KeyError, ctx.add_property, 'foo', 2)


def test_add_property_static():
    ctx = Context()
    ctx.add_property('foo', 'bar')
    assert ctx.foo == 'bar'


def test_add_property_no_cache():
    foo = Mock(return_value=1)
    ctx = Context()
    ctx.add_property('foo', foo, cached=False)
    assert ctx.foo == 1
    assert ctx.foo == 1
    foo.assert_has_calls([call(ctx), call(ctx)])


def test_mapper_add_ctx_property():
    foo = Mock(return_value=1)
    mapper = Mapper()
    mapper.add_ctx_property('foo', foo)

    def resource(request, ctx):
        ctx.foo
        ctx.foo
        return ok()

    mapper.add('/', resource)
    res = mapper(Request({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/'}))
    assert res.code == 200
    assert foo.call_count == 1


def test_mapper_add_ctx_property_duplicate():
    mapper = Mapper()
    mapper.add_ctx_property('foo', 1)
    assert_raises(InvalidArgumentError, mapper.add_ctx_property, 'foo', 2)


def test_callbacks():
    ctx = Context()
    cb = Mock()
    ctx.add_callback('enter', cb)
    ctx._run_callbacks('enter', 1, 2)
    cb.assert_has_calls([call(1, 2)])


def test_invalid_callback():
    ctx = Context()
    assert_raises(KeyError, ctx.add_callback, 'invalid', lambda: None)
