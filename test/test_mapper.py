# encoding: utf-8
import unittest

from rhino.mapper import Mapper, template2regex, template2path, \
        InvalidArgumentError, InvalidTemplateError
from rhino.response import Response

# Dispatcher and template2regex tests taken from Joe Gregorio's
# wsgidispatcher.py (https://code.google.com/p/robaccia/) with minor
# modifications.

Dispatcher = Mapper

class Test(unittest.TestCase):
    def setUp(self):
        self.called = False
        self.status = None
        self.app_number = 0

    def _start_response(self, status, response_headers, exc_info=None):
        self.status = status

    def _app(self, request):
        self.called = True
        self.environ = request.environ.copy()
        return Response(200, [], '')

    def _app1(self, request):
        self.app_number = 1
        return self._app(request)

    def _app2(self, request):
        self.app_number = 2
        return self._app(request)

    def _app3(self, request):
        self.app_number = 3
        return self._app(request)

    def test_happy_path(self):
        d = Dispatcher()
        d.add("/fred/", self._app)
        d.wsgi({'PATH_INFO': '/fred/', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertTrue(self.called)

    def test_happy_path_miss(self):
        d = Dispatcher()
        d.add("/fred/", self._app)
        d.wsgi({'PATH_INFO': '/fred', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)

    def test_zero_length_path(self):
        d = Dispatcher()
        d.add("", self._app)
        d.wsgi({'PATH_INFO': '', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertTrue(self.called)

    def test_template_simple(self):
        d = Dispatcher()
        d.add("/{fred}/", self._app)
        d.wsgi({'PATH_INFO': '/barney/', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertTrue(self.called)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['fred'], 'barney')

    def test_template_two_part(self):
        d = Dispatcher()
        d.add("/{name}/[{name2}/]", self._app)
        d.wsgi({'PATH_INFO': '//', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)
        d.wsgi({'PATH_INFO': '/fred', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)
        d.wsgi({'PATH_INFO': '/fred/barney', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)
        d.wsgi({'PATH_INFO': '/fred/barney/', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertTrue(self.called)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name'], 'fred')
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name2'], 'barney')

    def test_template_two_part_trailing(self):
        d = Dispatcher()
        d.add("/{name}/[{name2}/]|", self._app)
        d.wsgi({'PATH_INFO': '//', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)
        d.wsgi({'PATH_INFO': '/fred', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertFalse(self.called)
        d.wsgi({'PATH_INFO': '/fred/barney', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertTrue(self.called)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name'], 'fred')
        #self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name2'], None)
        self.assertTrue('name2' not in self.environ['wsgiorg.routing_args'][1])

    def test_template_new_char_range(self):
        d = Dispatcher({'real': '(\+|-)?[1-9]\.[0-9]*E(\+|-)?[0-9]+'})
        d.add("/{name:real}/", self._app)
        d.wsgi({'PATH_INFO': '/3.1415925535E-10/', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name'], '3.1415925535E-10')

    def test_real_world_examples(self):
        urls = Dispatcher()
        urls.add('/service/[{ctype:alpha}[/[{id:unreserved}/]]][;{noun}]', self._app1)
        urls.add('/comments/[{id:alnum}]',  self._app2)
        urls.add('/{alpha}/[{id}[/[{slug}]]]',  self._app3)

        urls.wsgi({'PATH_INFO': '/service/;service_document', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(1, self.app_number)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['noun'], 'service_document')
        self.app_number = 0

        urls.wsgi({'PATH_INFO': '/comments/2', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(2, self.app_number)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['id'], '2')
        self.app_number = 0

        urls.wsgi({'PATH_INFO': '/draft/98/My-slug_name', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(3, self.app_number)
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['slug'], 'My-slug_name')
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['id'], '98')

    def test_extreme_laziness(self):
        """No rules, no method, and no path_info. We should
        not throw an exception"""
        d = Dispatcher()
        d.wsgi({}, self._start_response)
        self.assertFalse(self.called)
        self.assertEqual(self.status, "404 Not Found")

    def test_semicolon(self):
        urls = Dispatcher()
        urls.add('/service/[{id:word}][;{noun}]', self._app)

        urls.wsgi({'PATH_INFO': '/service/fred;service_document', 'REQUEST_METHOD': 'GET'}, self._start_response)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['noun'], 'service_document')
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['id'], 'fred')

    def test_unicode(self):
        urls = Dispatcher()
        urls.add('/{name}', self._app)

        urls.wsgi({'PATH_INFO': u'/☃'.encode('utf-8')}, self._start_response)
        self.assertEqual(self.status, "200 OK")
        self.assertEqual(self.environ['wsgiorg.routing_args'][1]['name'], u'☃')


class Template2Regex(unittest.TestCase):

    def test_template_failures(self):
        cases = ('[][', '[]]', '{}{', '{}}', '|a', 'a|b')
        for template in cases:
            self.assertRaises(InvalidTemplateError, template2regex, template)

    def test_template_expand(self):
        cases = [
                ("{fred}", (r"^(?P<fred>[^/]+)$", ['fred'])),
                ("{fred:alpha}", (r"^(?P<fred>[a-zA-Z]+)$", ['fred'])),
                ("{fred:unreserved}", (r"^(?P<fred>[a-zA-Z\d\-\.\_\~]+)$", ['fred'])),
                ("{fred}|", (r"^(?P<fred>[^/]+)", ['fred'])),
                ("{fred}/{barney}|", (r"^(?P<fred>[^/]+)\/(?P<barney>[^/]+)", ['fred', 'barney'])),
                ("{fred}[/{barney}]|", (r"^(?P<fred>[^/]+)(\/(?P<barney>[^/]+))?", ['fred', 'barney'])),
                ("{fred}[/[{barney}]]|", (r"^(?P<fred>[^/]+)(\/((?P<barney>[^/]+))?)?", ['fred', 'barney'])),
                ("{fred}[/[{barney}]]", (r"^(?P<fred>[^/]+)(\/((?P<barney>[^/]+))?)?$", ['fred', 'barney'])),
                ("/{id}[/[{slug}]];edit_comment_form", (r"^\/(?P<id>[^/]+)(\/((?P<slug>[^/]+))?)?\;edit\_comment\_form$", ['id', 'slug'])),
                ("/service/[{ctype:alpha}[/[{id}/]]][;{noun}]", (r"^\/service\/((?P<ctype>[a-zA-Z]+)(\/((?P<id>[^/]+)\/)?)?)?(\;(?P<noun>[^/]+))?$", ['ctype', 'id', 'noun'])),
                ]
        for template, result in cases:
            self.assertEqual(template2regex(template), result)


class TestTemplate2Path(unittest.TestCase):

    def test_example(self):
        template = "/service/[{collection:alpha}[/[{id:unreserved}/]]][;{noun}]"
        self.assertEqual(template2path(template, {}), '/service/')
        self.assertEqual(template2path(template, {'collection':'posts'}), '/service/posts')
        self.assertEqual(template2path(template, {'collection':'posts', 'id':123}), '/service/posts/123/')
        self.assertEqual(template2path(template, {'collection':'posts', 'id':123, 'noun':'form'}), '/service/posts/123/;form')

    def test_params(self):
        template = "/{a}"
        self.assertEqual(template2path(template, {'a':'x'}), '/x')
        self.assertEqual(template2path(template, {'a':'x', 'b':'y'}), '/x')
        self.assertRaises(InvalidArgumentError, template2path, template, {})

    def test_ranges(self):
        template = "/[{a:myrange}]"
        self.assertEqual(template2path(template, {}), '/')
        self.assertEqual(template2path(template, {'a':1}, {'myrange':'\d+'}), '/1')
        self.assertRaises(InvalidArgumentError, template2path, template, {'a':'x'}, {'myrange':'\d+'})

    def test_brackets(self):
        template = "/[{a}]-[x]-[{b}]"
        self.assertEqual(template2path(template, {'a':1, 'b':2}), '/1--2')
        self.assertEqual(template2path(template, {'a':1       }), '/1--')
        self.assertEqual(template2path(template, {       'b':2}), '/--2')
        self.assertEqual(template2path(template, {            }), '/--')

    def test_nested_lr(self):
        template = "/[{a}[-{b}[-{c}]]/]x"
        self.assertEqual(template2path(template, {'a':1, 'b':2, 'c':3}), '/1-2-3/x')
        self.assertEqual(template2path(template, {'a':1, 'b':2       }), '/1-2/x')
        self.assertEqual(template2path(template, {'a':1              }), '/1/x')
        # unused optional parameters don't raise an exception
        self.assertEqual(template2path(template, {'a':1,        'c':3}), '/1/x')
        self.assertEqual(template2path(template, {       'b':2, 'c':3}), '/x')
        self.assertEqual(template2path(template, {              'c':3}), '/x')
        self.assertEqual(template2path(template, {       'b':2       }), '/x')

    def test_nested_rl(self):
        template = "/[[[{a}-]{b}-]{c}/]x"
        self.assertEqual(template2path(template, {'a':1, 'b':2, 'c':3}), '/1-2-3/x')
        self.assertEqual(template2path(template, {       'b':2, 'c':3}), '/2-3/x')
        self.assertEqual(template2path(template, {              'c':3}), '/3/x')
        # unused optional parameters don't raise an exception
        self.assertEqual(template2path(template, {'a':1,        'c':3}), '/3/x')
        self.assertEqual(template2path(template, {'a':1, 'b':2       }), '/x')
        self.assertEqual(template2path(template, {'a':1,             }), '/x')
        self.assertEqual(template2path(template, {       'b':2       }), '/x')

    def test_bar(self):
        self.assertEqual(template2path('/a|', {}), '/a')

    def test_quote_reserved(self):
        self.assertEqual(template2path('/{x:any}', {'x': 'foo:;/bar?a=1&b=2'}), '/foo:;/bar%3Fa%3D1%26b%3D2')

    def test_unicode(self):
        self.assertEqual(template2path('/{name}', {'name': u'☃'}), '/%E2%98%83')

    def test_template_failures(self):
        cases = ('[][', '[]]', '{x}{', '{x}}', '|a', 'a|b')
        for template in cases:
            self.assertRaises(InvalidTemplateError,
                    template2path, template, {'x': 1})


def test_path():
    app = Mapper()
    fn = lambda: None
    app.add('/', fn, 'test')
    assert app.path('test', {}, []) == '/'
    assert app.path(fn, {}, []) == '/'
