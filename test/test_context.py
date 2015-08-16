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
    assert_mock_has_no_calls(foo)
    assert ctx.foo == 1
    assert ctx.foo == 1
    foo.assert_has_calls([call()])


def test_add_property_not_cached():
    foo = Mock(return_value=1)
    ctx = Context()
    ctx.add_property('foo', foo, cached=False)
    assert ctx.foo == 1
    assert ctx.foo == 1
    foo.assert_has_calls([call(), call()])


def test_add_property_with_ctx():
    m = Mock(return_value=1)
    foo = lambda ctx: m(ctx)
    ctx = Context()
    ctx.add_property('foo', foo)
    assert ctx.foo == 1
    m.assert_has_calls([call(ctx)])


def test_invalid_property():
    ctx = Context()
    assert_raises(AttributeError, lambda: ctx.foo)


def test_add_property_duplicate():
    ctx = Context()
    ctx.add_property('foo', 1)
    assert_raises(KeyError, ctx.add_property, 'foo', 2)


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


def test_config():
    mapper = Mapper()
    mapper.config['some.value'] = 'foo'

    def resource(request, ctx):
        return ok(ctx.config['some.value'])

    mapper.add('/', resource)
    res = mapper(Request({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/'}))
    assert res.code == 200
    assert res.body == 'foo'


def test_callbacks():
    ctx = Context()
    cb = Mock()
    ctx.add_callback('enter', cb)
    ctx._run_callbacks('enter', 1, 2)
    cb.assert_has_calls([call(1, 2)])


def test_invalid_callback():
    ctx = Context()
    assert_raises(KeyError, ctx.add_callback, 'invalid', lambda: None)


def test_wrapper_access_to_ctx_properties():
    def test_wrapper(app):
        def wrapper(req, ctx):
            assert ctx.foo == 1
            return app(req, ctx)
        return wrapper

    foo = Mock(return_value=1)
    mapper = Mapper()
    mapper.add_ctx_property('foo', foo)
    mapper.add_wrapper(test_wrapper)
    mapper.add('/', lambda _: ok())
    res = mapper(Request({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/'}))
    assert res.code == 200
    assert foo.has_calls([call()])


def test_wrapper_access_to_ctx_config():
    def test_wrapper(app):
        def wrapper(req, ctx):
            assert ctx.config['foo'] == 1
            return app(req, ctx)
        return wrapper

    foo = Mock(return_value=1)
    mapper = Mapper()
    mapper.config['foo'] = 1
    mapper.add_wrapper(test_wrapper)
    mapper.add('/', lambda _: ok())
    res = mapper(Request({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/'}))
    assert res.code == 200
