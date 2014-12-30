from rhino.mapper import Mapper
from rhino.urls import request_context, build_url


def test_build_url():
    mapper = Mapper()
    mapper.add('/foo', 1, 'foo')

    context = [request_context('', mapper, mapper.routes[0])]

    assert build_url(context, '/')    == '/'
    assert build_url(context, '.')    == '/foo'
    assert build_url(context, 'foo')  == '/foo'
    assert build_url(context, '.foo') == '/foo'
    assert build_url(context, '/foo') == '/foo'
    assert build_url(context, 1)      == '/foo'


def test_build_url_nested():
    mapper1 = Mapper()
    mapper2 = Mapper()
    mapper2.add('/bar', 1, 'bar')
    mapper1.add('/foo|', mapper2, 'foo')

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
