from pytest import raises as assert_raises
from rhino.mapper import Mapper, InvalidArgumentError
from rhino.urls import request_context, build_url


def test_build_url():
    mapper = Mapper()
    mapper.add('/foo', None, 'foo')

    context = [request_context('', mapper, mapper.routes[0])]

    assert build_url(context, '/')    == '/'
    assert build_url(context, '.')    == '/foo'
    assert build_url(context, 'foo')  == '/foo'
    assert build_url(context, '.foo') == '/foo'
    assert build_url(context, '/foo') == '/foo'
    assert build_url(context, None)   == '/foo'


def test_build_url_nested():
    mapper1 = Mapper()
    mapper2 = Mapper()
    mapper1.add('/foo|', mapper2, 'foo')
    mapper2.add('/bar', None, 'bar')

    context = [request_context('',     mapper1, mapper1.routes[0]),
               request_context('/foo', mapper2, mapper2.routes[0])]

    assert build_url(context, '/')         == '/'
    assert build_url(context, '/foo')      == '/foo'
    assert build_url(context, '/foo.bar')  == '/foo/bar'
    assert build_url(context, '.')         == '/foo/bar'
    assert build_url(context, 'bar')       == '/foo/bar'
    assert build_url(context, '.bar')      == '/foo/bar'
    assert build_url(context, '..foo')     == '/foo'
    assert build_url(context, '..foo.bar') == '/foo/bar'


def test_build_url_params_named():
    mapper1 = Mapper()
    mapper2 = Mapper()
    mapper1.add('/a/{p1}[/{p2}]|', mapper2, 'a')
    mapper2.add('/b/{p3}[/{p4}]', None, 'b')

    context = [request_context('', mapper1, mapper1.routes[0])]

    assert build_url(context, '/a', [], dict(p1=11, p2=22)) == '/a/11/22'
    assert build_url(context, '/a.b', [], dict(p1=11, p3=33)) == '/a/11/b/33'
    assert build_url(context, '/a.b',
            [], dict(p1=11, p2=22, p3=33)) == '/a/11/22/b/33'
    assert build_url(context, '/a.b',
            [], dict(p1=11, p2=22, p3=33, p4=44)) == '/a/11/22/b/33/44'


def test_build_url_params_positional():
    mapper1 = Mapper()
    mapper2 = Mapper()
    mapper1.add('/a/{p1}[/{p2}]|', mapper2, 'a')
    mapper2.add('/b/{p3}[/{p4}]', None, 'b')

    context = [request_context('', mapper1, mapper1.routes[0])]

    assert build_url(context, '/a', [11]) == '/a/11'
    assert build_url(context, '/a', [11, 22]) == '/a/11/22'
    assert_raises(InvalidArgumentError,
            build_url, context, '/a', [11, 22, 33])

    assert build_url(context, '/a.b', [11, 22, 33, 44]) == '/a/11/22/b/33/44'
    assert build_url(context, '/a.b', [11, 22, 33]) == '/a/11/22/b/33'
    assert_raises(InvalidArgumentError,
            build_url, context, '/a.b', [11, 22])


def test_build_url_params_mixed():
    mapper1 = Mapper()
    mapper2 = Mapper()
    mapper1.add('/a/{p1}[/{p2}]|', mapper2, 'a')
    mapper2.add('/b/{p3}[/{p4}]', None, 'b')

    context = [request_context('', mapper1, mapper1.routes[0])]
    assert build_url(context, '/a', [22], dict(p1=11)) == '/a/11/22'
    assert build_url(context, '/a', [11], dict(p2=22)) == '/a/11/22'
    assert_raises(InvalidArgumentError,
            build_url, context, '/a', [11, 22], dict(p1=11))
    assert_raises(InvalidArgumentError,
            build_url, context, '/a', [11], dict(p1=11, p2=22))

    assert build_url(context, '/a.b', [22, 44], dict(p1=11, p3=33)) \
            == '/a/11/22/b/33/44'
    assert build_url(context, '/a.b', [22], dict(p1=11, p3=33)) \
            == '/a/11/22/b/33'
