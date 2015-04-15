# encoding: utf-8
import time
from datetime import datetime, timedelta
from wsgiref.util import setup_testing_defaults

import mock
from mock import patch
from pytest import raises as assert_raises
from rhino.response import Entity, Response, \
        response, ok, created, no_content, redirect, \
        datetime_to_httpdate
from rhino.request import Request


def wsgi_response(response, environ=None):
    if environ is None:
        environ = {}
    rv = []

    def start_response(*args):
        rv.extend(args)

    app_iter = response(environ, start_response)
    body = ''.join(app_iter)
    if hasattr(app_iter, 'close'):
        app_iter.close()
    status, headers = rv
    return status, headers, body


def test_defaults():
    res = Response(200)
    assert res.code == 200
    assert res.status == "200 OK"
    assert res.headers.items() == []
    assert res.body == ''


def test_finalize():
    status, headers, body = wsgi_response(Response(200))
    assert status == "200 OK"
    assert headers == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '0')
    ]
    assert body == ''


def test_finalize_invalid():
    assert_raises(TypeError, wsgi_response, Response(200, body=dict()))
    assert_raises(TypeError, wsgi_response, Response(200, body=list()))
    assert_raises(TypeError, wsgi_response, Response(200, body=tuple()))
    assert_raises(TypeError, wsgi_response, Response(200, body=object()))


def test_finalize_head():
    status, headers, body = wsgi_response(
            Response(200, body='test'), {'REQUEST_METHOD': 'HEAD'})
    assert status == "200 OK"
    assert headers == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '4')
    ]
    assert body == ''

    status, headers, body = wsgi_response(
            Response(200, body='test'), {'REQUEST_METHOD': 'head'})
    assert body == ''


def test_finalize_lazy():
    body = lambda: 'test'
    status, headers, body = wsgi_response(Response(200, body=body))
    assert status == "200 OK"
    assert headers == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '4')
    ]
    assert body == 'test'


def test_finalize_lazy_unicode():
    body = lambda: u'★'
    status, headers, body = wsgi_response(Response(200, body=body))
    assert status == "200 OK"
    assert headers == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(u'★'.encode('utf-8'))))
    ]
    assert body == u'★'.encode('utf-8')


def test_finalize_lazy_invalid():
    body = lambda: None
    assert_raises(TypeError, wsgi_response, Response(200, body=body))


def test_entity():
    entity = Entity('test', content_type='text/html')
    assert entity.body == 'test'
    assert entity.headers.items() == [('Content-Type', 'text/html')]


def test_response_from_entity():
    entity = Entity('test', content_type='text/html')

    status, headers, body = wsgi_response(Response(200, body=entity))
    assert headers == [
        ('Content-Type', 'text/html'),
        ('Content-Length', '4'),
    ]

    status, headers, body = wsgi_response(response(200, body=entity,
                                content_type='text/plain'))
    assert headers == [
        ('Content-Type', 'text/plain'),
        ('Content-Length', '4'),
    ]


def test_headers():
    environ = {}
    setup_testing_defaults(environ)
    res = Response(200, [('X-Foo', u'Smørebrød'), ('Location', u'/☃')], u'☃')
    status, headers, body = wsgi_response(res, environ)
    assert status == "200 OK"
    assert headers == [
        ('X-Foo', u'Smørebrød'.encode('latin-1')),
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(u'☃'.encode('utf-8')))),
        ('Location', 'http://127.0.0.1/%E2%98%83'),
    ]
    assert body == u'☃'.encode('utf-8')


def test_location_is_absolute():
    environ = {}
    setup_testing_defaults(environ)
    res = Response(302, [('Location', 'http://foo.com/bar;quux?a=b&c=1#x')], '')
    status, headers, body = wsgi_response(res, environ)
    assert headers == [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', '0'),
        ('Location', 'http://foo.com/bar;quux?a=b&c=1#x'),
    ]


def test_close_callbacks():
    class callback(object):
        def __init__(self):
            self.called = False

        def __call__(self):
            self.called = True

    environ = {}
    setup_testing_defaults(environ)

    cb = callback()
    res = response(200, body='test')
    res.add_callback(cb)
    status, headers, body = wsgi_response(res, environ)
    assert body == 'test'
    assert cb.called


def test_set_cookie_defaults():
    res = response(200)
    res.set_cookie('foo', 'bar')
    assert res.headers.get_all('Set-Cookie') == ['foo=bar; Path=/']


def test_set_cookie_all():
    res = response(200)
    res.set_cookie(
        key='a',
        value=u'Smørebrød',
        max_age=600,
        path='/test',
        domain='example.net',
        secure=True,
        httponly=True,
        expires=datetime(2012, 12, 8, 0, 0, 0),
    )
    cookies = res.headers.get_all('Set-Cookie')
    assert len(cookies) == 1
    # The 'expires' date format in the stdlib's cookie module was fixed
    # in a 2.7 point release.
    assert cookies[0] in [
        'a="Sm\\303\\270rebr\\303\\270d"; Domain=example.net; expires=Sat, 08-Dec-2012 00:00:00 GMT; httponly; Max-Age=600; Path=/test; secure',
        'a="Sm\\303\\270rebr\\303\\270d"; Domain=example.net; expires=Sat, 08 Dec 2012 00:00:00 GMT; httponly; Max-Age=600; Path=/test; secure',
    ]


def test_set_cookie_timedelta():
    res = response(200)
    res.set_cookie('foo', 'bar', max_age=timedelta(minutes=5))
    assert res.headers.get_all('Set-Cookie') == ['foo=bar; Max-Age=300; Path=/']

    res = response(200)
    with patch.object(time, 'time') as mock_time:
        mock_time.return_value = 1.0
        res.set_cookie('foo', 'bar', expires=timedelta(minutes=5))
    cookies = res.headers.get_all('Set-Cookie')
    assert len(cookies) == 1
    # The 'expires' date format in the stdlib's cookie module was fixed
    # in a 2.7 point release.
    assert cookies[0] in [
        'foo=bar; expires=Thu, 01-Jan-1970 00:05:01 GMT; Path=/',
        'foo=bar; expires=Thu, 01 Jan 1970 00:05:01 GMT; Path=/',
    ]

def test_delete_cookie():
    res = response(200)
    res.delete_cookie('x', path='/', domain='example.net')
    cookies = res.headers.get_all('Set-Cookie')
    assert len(cookies) == 1
    # The 'expires' date format in the stdlib's cookie module was fixed
    # in a 2.7 point release.
    assert cookies[0] in [
        'x=; Domain=example.net; expires=Thu, 01-Jan-1970 00:00:00 GMT; Max-Age=0; Path=/',
        'x=; Domain=example.net; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/',
    ]


def test_conditional_to_etag():
    orig = response(200, 'test', etag='0xdecafbad')

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xdecafbad"'}))
    assert res.code == 304
    assert res.body == ''
    assert res.headers['Etag'] == '"0xdecafbad"'

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xabad1dea"'}))
    assert res is orig


def test_conditional_to_etag_404():
    orig = response(404, 'not found', etag='0xdecafbad')

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xdecafbad"'}))
    assert res is orig


def test_conditional_to_last_modified():
    dt = datetime(2014, 4, 1, 12, 0)
    dt2 = dt - timedelta(seconds=1)
    orig = response(200, 'test', last_modified=dt)

    res = orig.conditional_to(Request({'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt)}))
    assert res.code == 304
    assert res.body == ''
    assert res.headers['Last-Modified'] is None

    res = orig.conditional_to(Request({'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt2)}))
    assert res is orig

    res = orig.conditional_to(Request({'HTTP_IF_MODIFIED_SINCE': 'invalid'}))
    assert res is orig


def test_etag_and_last_modified():
    dt = datetime(2014, 4, 1, 12, 0)
    dt2 = dt - timedelta(seconds=1)
    orig = response(200, 'test', last_modified=dt, etag='0xdecafbad')

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xdecafbad"'}))
    assert res.code == 304

    res = orig.conditional_to(Request({'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt)}))
    assert res.code == 304

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xdecafbad"', 'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt)}))
    assert res.code == 304

    # FIXME Should matching ETag take precedence (see comment below)?
    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xabad1dea"', 'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt)}))
    assert res is orig

    res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xabad1dea"', 'HTTP_IF_MODIFIED_SINCE': datetime_to_httpdate(dt2)}))
    assert res is orig

    # FIXME It makes sense that ETag should take precedence here, but I think the spec says both conditions must match if both
    # headers are present.
    #res = orig.conditional_to(Request({'HTTP_IF_NONE_MATCH': '"0xdecafbad"', 'HTTP_IF_MODIFIED_SINCE': 'invalid'}))
    #assert res.code == 304


def test_response_defaults():
    res = response(200)
    assert res.code == 200
    assert res.body == ''


def test_response_last_modified():
    dt = datetime.utcnow()
    res = response(200, last_modified=dt)
    assert res.headers['Last-Modified'] == datetime_to_httpdate(dt)

    res = response(200, last_modified=None)
    assert 'Last-Modified' not in res.headers


def test_response_etag():
    res = response(200, etag='foo')
    assert res.headers['ETag'] == '"foo"'

    res = response(200, etag='"foo"')
    assert res.headers['ETag'] == '"foo"'

    res = response(200, etag=None)
    assert 'Etag' not in res.headers

    assert_raises(TypeError, response, 200, etag=123)


def test_response_expires():
    dt = datetime.utcnow() + timedelta(seconds=60)

    res = response(200, expires=60)
    assert res.headers['Expires'] == datetime_to_httpdate(dt)

    res = response(200, expires=timedelta(seconds=60))
    assert res.headers['Expires'] == datetime_to_httpdate(dt)

    res = response(200, expires=dt)
    assert res.headers['Expires'] == datetime_to_httpdate(dt)


def test_ok():
    res = ok()
    assert res.code == 200

    res = ok('hi', code=201, x_foo='bar', etag='x')
    assert res.code == 201
    assert res.body == 'hi'
    assert res.headers['X-Foo'] == 'bar'
    assert res.headers['Etag'] =='"x"'

    assert_raises(ValueError, ok, code=199)
    assert_raises(ValueError, ok, code=300)


def test_created():
    res = created()
    assert res.code == 201


def test_no_content():
    res = no_content()
    assert res.code == 204
    assert_raises(TypeError, no_content, body='test')


def test_redirect():
    assert_raises(TypeError, redirect)

    res = redirect('/')
    assert res.code == 302
    assert res.headers.items() == [('Location', '/')]

    res = redirect('/foo', code=301, x_foo='bar')
    assert res.code == 301
    assert res.headers['Location'] == '/foo'
    assert res.headers['X-Foo'] == 'bar'

    assert_raises(ValueError, redirect, '/', code=299)
    assert_raises(ValueError, redirect, '/', code=400)


def test_conditional_lazy_body():
    mock_body = mock.create_autospec(lambda: None, return_value='ok')
    res = response(200, body=mock_body, etag='1')

    req = Request({'HTTP_IF_NONE_MATCH': '"1"'})
    status, _, body = wsgi_response(res.conditional_to(req), req.environ)
    assert status == "304 Not Modified"
    assert body == ''
    assert not mock_body.called

    req = Request({'HTTP_IF_NONE_MATCH': '"2"'})
    status, _, body = wsgi_response(res.conditional_to(req), req.environ)
    assert status == "200 OK"
    assert body == 'ok'
    assert mock_body.called
