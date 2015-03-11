# encoding: utf-8
from StringIO import StringIO
from wsgiref.util import setup_testing_defaults

import rhino
from mock import patch
from pytest import fixture, raises as assert_raises
from rhino.request import Request, QueryDict, WsgiInput

body = 'x=1&x=2&%E2%98%85=%E2%98%83'
body_multipart = u'''--xxx
Content-Disposition: form-data; name="★"

☃
--xxx
Content-Disposition: form-data; name="★★"; filename="☃.txt"
Content-Type: text/plain

☃☃☃
--xxx--'''.encode('utf-8')

@fixture
def environ():
    environ = {
        'REQUEST_METHOD': 'post',
        # SCRIPT_NAME and PATH_INFO are unquoted in the WSGI environment
        'SCRIPT_NAME': u'/☃'.encode('utf-8'),
        'PATH_INFO': u'/★'.encode('utf-8'),
        'QUERY_STRING': 'a=1&a=2&b=%E2%98%83&c',
        'HTTP_X_FOO': u'Smørebrød'.encode('latin-1'),
        'HTTP_COOKIE': 'x="\\342\\230\\203"; a=b',
        'CONTENT_TYPE': 'application/x-www-form-urlencoded',
        'CONTENT_LENGTH': str(len(body)),
        'REMOTE_ADDR': '1.2.3.4',
        'REMOTE_PORT': '12345',
        'wsgi.input': StringIO(body),
    }
    setup_testing_defaults(environ)
    return environ

@fixture
def environ_multipart():
    environ_multipart = {
        'REQUEST_METHOD': 'POST',
        'CONTENT_TYPE': 'multipart/form-data; boundary=xxx',
        'CONTENT_LENGTH': str(len(body_multipart)),
        'wsgi.input': StringIO(body_multipart),
    }
    setup_testing_defaults(environ_multipart)
    return environ_multipart


def test_defaults():
    req = Request({})
    assert req.method == 'GET'
    assert 'Content-Length' not in req.headers
    assert req.content_length == None


def test_empty_content_length():
    req = Request({'CONTENT_LENGTH': ''})
    assert req.content_length == None


def test_bad_content_length():
    req = Request({'CONTENT_LENGTH': 'test'})
    assert req.content_length == None


def test_wsgi_input():
    data = 'foo\nbar'
    f = WsgiInput(StringIO(data), content_length=len(data))
    assert f.read() == 'foo\nbar'

    f = WsgiInput(StringIO(data), content_length=len(data))
    assert f.read(3) == 'foo'
    assert f.read() == '\nbar'

    f = WsgiInput(StringIO(data), content_length=len(data))
    assert f.readline() == 'foo\n'
    assert f.readline() == 'bar'
    assert f.readline() == ''

    f = WsgiInput(StringIO(data), content_length=len(data))
    assert f.readlines() == ['foo\n', 'bar']

    f = WsgiInput(StringIO(data), content_length=len(data))
    assert list(f) == ['foo\n', 'bar']


def test_request_input(environ):
    req = Request(environ)
    assert isinstance(req.input, WsgiInput)
    assert req.input.read() == body
    assert req.input.read() == ''
    assert req.form.items() == []
    assert req.body == ''


def test_request_input_no_wrap(environ):
    req = Request(environ)
    req.wrap_wsgi_input = False
    assert isinstance(req.input, StringIO)
    assert req.input.read() == body
    assert req.input.read() == ''
    assert req.form.items() == []
    assert req.body == ''


def test_request_body(environ):
    req = Request(environ)
    assert req.body == body
    assert req.body == body
    assert req.form.items() == []
    assert req.input.read() == ''


def test_request_form(environ):
    req = Request(environ)
    assert req.form.items() == [('x', '1'), ('x', '2'), (u'★', u'☃')]
    assert req.form.items() == [('x', '1'), ('x', '2'), (u'★', u'☃')]
    assert req.body == ''
    assert req.input.read() == ''


def test_accessors(environ):
    req = Request(environ)
    assert req.method == 'POST'
    assert req.script_name == u'/☃'
    assert req.path_info == u'/★'
    # TODO Decode url?
    assert req.url == 'http://127.0.0.1/%E2%98%83/%E2%98%85?a=1&a=2&b=%E2%98%83&c'
    assert req.content_type == 'application/x-www-form-urlencoded'
    assert req.content_length == len(body)
    assert req.server_name == '127.0.0.1'
    assert req.server_port == 80
    assert req.server_protocol == 'HTTP/1.0'
    assert req.scheme == 'http'
    assert req.query.items() == [('a', '1'), ('a', '2'), ('b', u'☃'), ('c', '')]
    assert req.cookies['x'] == u'☃'
    assert req.cookies['a'] == 'b'
    assert req.remote_addr == '1.2.3.4'
    assert req.remote_port == 12345


def test_request_headers(environ):
    headers = Request(environ).headers
    content_length = str(len(body))
    assert headers['Host'] == '127.0.0.1'
    assert headers['hOST'] == '127.0.0.1'
    assert headers['Content-Type'] == 'application/x-www-form-urlencoded'
    assert headers['cONTENT-tYPE'] == 'application/x-www-form-urlencoded'
    assert headers['Content-Length'] == content_length
    assert headers['cONTENT-lENGTH'] == content_length
    assert 'no-such-header' not in headers
    assert headers['X-Foo'] == u'Smørebrød'
    assert set(headers.keys()) == set([
        'Host', 'Content-Type', 'Content-Length', 'X-Foo', 'Cookie',
    ])
    assert set(headers.values()) == set([
        '127.0.0.1', 'application/x-www-form-urlencoded', content_length,
        u'Smørebrød', 'x="\\342\\230\\203"; a=b',
    ])
    assert sorted(headers.items()) == [
        ('Content-Length', content_length),
        ('Content-Type', 'application/x-www-form-urlencoded'),
        ('Cookie', 'x="\\342\\230\\203"; a=b'),
        ('Host', '127.0.0.1'),
        ('X-Foo', u'Smørebrød'),
    ]
    assert len(headers) == 5


def test_mutable_routing_args():
    req = Request({})
    assert req.routing_args == {}
    req.routing_args['bar'] = 1
    assert req.routing_args == {'bar': 1}


def test_querydict():
    q = QueryDict([])
    assert 'z' not in q
    with assert_raises(KeyError):
        q['z']

    q = QueryDict([('a', 1), ('a', 2), ('b', 3)])
    assert q.keys() == ['a', 'a', 'b']
    assert q.values() == [1, 2, 3]
    assert q.items() == [('a', 1), ('a', 2), ('b', 3)]
    assert list(q.iteritems()) == q.items()
    assert list(q.iterkeys()) == q.keys()
    assert list(q.itervalues()) == q.values()
    assert 'a' in q
    assert q['a'] == 1
    assert q.get('a') == 1
    assert q.getall('a') == [1, 2]
    assert q.getall('a') == q.getlist('a')
    assert list(q) == ['a', 'a', 'b']
    assert len(q) == 3

    q = QueryDict([('foo', None)])
    assert 'foo' in q
    assert q['foo'] is None


def test_file_upload(environ_multipart):
    req = Request(environ_multipart)
    assert set(req.form.keys()) == set([u'★', u'★★'])
    assert req.form[u'★'] == u'☃'
    assert req.form[u'★★'].filename == u'☃.txt'
    assert req.form[u'★★'].type == 'text/plain'
    assert req.form[u'★★'].file.read() == u'☃☃☃'.encode('utf-8')


def test_url_for(environ):
    req = Request(environ)
    with patch.object(rhino.request, 'build_url') as mock_url:
        mock_url.return_value = '/'
        assert req.url_for('/') == 'http://127.0.0.1/'
        assert req.url_for('/', _query={'foo': 'bar'}) == 'http://127.0.0.1/?foo=bar'
        assert req.url_for('/', _query=[('foo', 1), ('foo', 2)]) == 'http://127.0.0.1/?foo=1&foo=2'
        assert req.url_for('/', _relative=True) == '/'
