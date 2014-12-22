"""
* Patterns are matched in the order in which they are added to the Dispatcher.
* First match wins

By default, a template parameter matches anything up to the next '/' character.

You can add an optional range qualifier to every template
parameter that restricts the characters that consistitute
a match. The range specifier follows a colon in the template name.
Here are the ranges that are predefined:

+-----------+--------------------+
|Range      |Regular Expression  |
+===========+====================+
|word       |\w+                 | 
+-----------+--------------------+
|alpha      |[a-zA-Z]+           |
+-----------+--------------------+
|digits     |\d+                 |
+-----------+--------------------+
|alnum      |[a-zA-Z0-9]+        |
+-----------+--------------------+
|segment    |[^/]+               |
+-----------+--------------------+
|unreserved |[a-zA-Z\d\-\.\_\~]+ |
+-----------+--------------------+
|any        |.+                  |
+-----------+--------------------+

Templates understand three special kinds of markup:

    +--------+-------------------------------------------------------------------------------------------------------------------+
    | {name} | Whatever matches this part of the path will be available to the application in the routing_args named parameters. | 
    +--------+-------------------------------------------------------------------------------------------------------------------+
    | []     | Any part of a path enclosed in brackets is optional                                                               |
    +--------+-------------------------------------------------------------------------------------------------------------------+ 
    | \|     | The bar may only be present at the end of the template and signals that the path need not match the whole path.   |
    +--------+-------------------------------------------------------------------------------------------------------------------+

    * Brackets may be nested
    * Brackets may contain template parameters

"""
from __future__ import absolute_import

import re
import sys
import urllib

from .errors import HTTPException, InternalServerError, NotFound
from .request import Request
from .util import get_args

# template2regex function taken from Joe Gregorio's wsgidispatcher.py
# (https://code.google.com/p/robaccia/) with minor modifications.

class MapperException(Exception): pass
class InvalidArgumentError(MapperException): pass
class InvalidTemplateError(MapperException): pass

template_splitter = re.compile("([\[\]\{\}\|])")
string_types = (str, unicode)

DEFAULT_RANGES = {
    'word': r'\w+',
    'alpha': r'[a-zA-Z]+',
    'digits': r'\d+',
    'alnum': r'[a-zA-Z0-9]+',
    'segment': r'[^/]+',
    'unreserved': r'[a-zA-Z\d\-\.\_\~]+',
    'any': r'.+'
}

# The conversion done in template2regex can be in one of two states, either
# handling a path, or it can be inside a {} template.
# The conversion done in template2path can additionaly be skipping an
# optional [] block.
S_PATH = 0
S_TEMPLATE = 1
S_SKIP = 2


def template2regex(template, ranges=None):
    """
    Converts a template, such as /{name}/ to a regular expression, e.g.
    /(?P<name>[^/]+)/ and a list of the named parameters found in the template
    (e.g. ['name']).
    Ranges are given after a colon in a template name to indicate a restriction
    on the characters that can appear there. For example, in the template::

        "/user/{id:alpha}"

    The ``id`` must contain only characters from a-zA-Z. Other characters there
    will cause the pattern not to match.

    The ranges parameter is an optional dictionary that maps range names to
    regular expressions. New range names can be added, or old range names can
    be redefined using this parameter.

    Example:

        >>> import rhino.mapper
        >>> rhino.mapper.template2regex("{fred}")
        ('^(?P<fred>[^/]+)$', ['fred'])

    This function is used internally by rhino.Mapper.
    """
    if len(template) and -1 < template.find('|') < len(template) - 1:
        raise InvalidTemplateError("'|' may only appear at the end, found at position %d in %s" % (template.find('|'), template))
    if ranges is None:
        ranges = DEFAULT_RANGES
    anchor = True
    state = S_PATH
    if len(template) and template[-1] == '|':
        anchor = False
    params = []

    bracketdepth = 0
    result = ['^']
    name = ""
    pattern = "[^/]+"
    rangename = None
    for c in template_splitter.split(template):
        if state == S_PATH:
            if len(c) > 1:
                result.append(re.escape(c))
            elif c == '[':
                result.append("(")
                bracketdepth += 1
            elif c == ']':
                bracketdepth -= 1
                if bracketdepth < 0:
                    raise InvalidTemplateError("Mismatched brackets in %s" % template)
                result.append(")?")
            elif c == '{':
                name = ""
                state = S_TEMPLATE
            elif c == '}':
                raise InvalidTemplateError("Mismatched braces in %s" % template)
            elif c == '|':
                pass
            else:
                result.append(re.escape(c))
        else:
            if c == '}':
                if rangename and rangename in ranges:
                    result.append("(?P<%s>%s)" % (name, ranges[rangename]))
                else:
                    result.append("(?P<%s>%s)" % (name, pattern))
                params.append(name)
                state = S_PATH
                rangename = None
            else:
                name = c
                if name.find(":") > -1:
                    name, rangename = name.split(":")
    if bracketdepth != 0:
        raise InvalidTemplateError("Mismatched brackets in %s" % template)
    if state == S_TEMPLATE:
        raise InvalidTemplateError("Mismatched braces in %s" % template)
    if anchor:
        result.append('$')
    return "".join(result), params


def template2path(template, params, ranges=None):
    """
    Converts a template, such as /{name}/ and a dictionary of parameter
    values to a path (string). Parameter values will be converted to
    strings and escaped.

      - param values that are used are validated against their range
      - unused parameters are ignored
      - optional ([]) blocks are skipped unless they contain one or more
        parameters and all of them are present in 'params'.
      - handles nested [] blocks

    Example:

        >>> import rhino.mapper
        >>> rhino.mapper.template2path("/{name}", {'name': 'fred'})
        '/fred'

    """
    if len(template) and -1 < template.find('|') < len(template) - 1:
        raise InvalidTemplateError("'|' may only appear at the end, found at position %d in %s" % (template.find('|'), template))
    if ranges is None:
        ranges = DEFAULT_RANGES

    # Stack for path components. A new list is added for each '[]' block
    # encountered. When the closing ']' is reached, the last element is
    # removed and either merged into the previous one (we keep the
    # block) or discarded (we skip the block). At the end, this should
    # contain a flat list of strings as its single element.
    stack = [[]]
    pattern = "[^/]+"    # default range
    name = ""            # name of the current parameter
    bracketdepth = 0     # current level of nested brackets
    skip_to_depth = 0    # if > 1, skip until we're back at this bracket level
    state = S_PATH
    rangename = None     # range name for the current parameter
    seen_name = [False]  # have we seen a named param in bracket level (index)?

    for c in template_splitter.split(template):
        if state == S_PATH:
            if len(c) > 1:
                stack[-1].append(c)
            elif c == '[':
                bracketdepth += 1
                stack.append([])
                seen_name.append(False)
            elif c == ']':
                bracketdepth -= 1
                if bracketdepth < 0:
                    raise InvalidTemplateError("Mismatched brackets in %s" % template)
                last_elem = stack.pop()
                if seen_name.pop():
                    stack[-1].extend(last_elem)
                    seen_name[-1] = True
            elif c == '{':
                name = ""
                state = S_TEMPLATE
            elif c == '}':
                raise InvalidTemplateError("Mismatched braces in %s" % template)
            elif c == '|':
                pass
            else:
                stack[-1].append(c)
        elif state == S_SKIP:
            if c == '[':
                bracketdepth += 1
                seen_name.append(False)
            elif c == ']':
                if bracketdepth == skip_to_depth:
                    stack.pop()
                    skip_to_depth = 0
                    state = S_PATH
                bracketdepth -= 1
                seen_name.pop()
        else:  # state == S_TEMPLATE
            if c == '}':
                if name not in params:
                    if bracketdepth:
                        # We're missing a parameter, but it's ok since
                        # we're inside a '[]' block. Skip everything
                        # until we reach the end of the current block.
                        skip_to_depth = bracketdepth
                        state = S_SKIP
                    else:
                        raise InvalidArgumentError("Missing parameter '%s' in %s" % (name, template))
                else:
                    if rangename and rangename in ranges:
                        regex = ranges[rangename]
                    else:
                        regex = pattern
                    value_bytes = unicode(params[name]).encode('utf-8')
                    value = urllib.quote(value_bytes, safe='/:;')
                    if not re.match('^' + regex + '$', value):
                        raise InvalidArgumentError("Value '%s' for parameter '%s' does not match '^%s$' in %s" % (value, name, regex, template))
                    stack[-1].append(value)
                    state = S_PATH
                rangename = None
            else:
                name = c
                if name.find(":") > -1:
                    name, rangename = name.split(":")
                seen_name[bracketdepth] = True

    if bracketdepth != 0:
        raise InvalidTemplateError("Mismatched brackets in %s" % template)
    if state == S_TEMPLATE:
        raise InvalidTemplateError("Mismatched braces in %s" % template)
    # None of these Should Ever Happen [TM]
    if state == S_SKIP:     # pragma: no cover
        raise MapperException("Internal error: end state is S_SKIP")
    if len(stack) > 1:      # pragma: no cover
        raise MapperException("Internal error: stack not empty")
    if len(seen_name) != 1: # pragma: no cover
        raise MapperException("Internal error: seen_name not empty")

    return "".join(stack[0])



_callback_phases = ['enter', 'leave', 'finalize', 'teardown', 'close']

def _callback_dict():
    return dict((k, []) for k in _callback_phases)


class Context(object):
    def __init__(self, request=None):
        self.request = request
        self.__properties = {}
        self.__callbacks = _callback_dict()

    def add_callback(self, phase, fn):
        """Add a callback to run in a specific phase.

        Possible values for phase:

            Phase       Callback arguments  Description of where and when it is called
            =======================================================================================================
            'enter'     request             In resource, after handler has been resolved but before it is run
            'leave'     request, response   In resource, after handler has returned successfully
            'finalize'  request, response   In mapper, before response body and headers are finalized
            'teardown'  -                   In mapper, before WSGI response is returned
            'close'     -                   In the WSGI server, when it calls close() on the WSGI response iterator

        """
        try:
            self.__callbacks[phase].append(fn)
        except KeyError:
            raise KeyError("Invalid callback phase '%s'. Must be one of %s" % (phase, _callback_phases))

    def _run_callbacks(self, phase, *args):
        for fn in self.__callbacks[phase]:
            fn(*args)

    def add_property(self, name, fn, cached=True):
        if name in self.__properties:
            raise KeyError("Trying to add a property '%s' that already exists on this %s instance." % (name, self.__class__.__name__))
        self.__properties[name] = (fn, cached)
        if not callable(fn):
            setattr(self, name, fn)

    def __getattr__(self, name):
        if name not in self.__properties:
            raise AttributeError("'%s' object has no attribute '%s'"
                    % (self.__class__.__name__, name))
        fn, cached = self.__properties[name]
        value = fn(self)
        if cached:
            setattr(self, name, value)
        return value


class Route(object):
    """
    A Route links a URL template with an optional name and view to a resource.

    Routes are used internally by rhino.Mapper, and are not part of the
    public API.
    """

    def __init__(self, template, resource, ranges=None, name=None, view=None):
        if ranges is None:
            ranges = DEFAULT_RANGES
        if name is not None and ('.' in name or '/' in name):
            raise InvalidArgumentError("Route name '%s' contains invalid characters ('.', '/')" % name)

        regex, params = template2regex(template, ranges)
        self.regex = re.compile(regex)
        self.params = set(params)
        self.template = template
        self.resource = resource
        self.ranges = ranges
        self.name = name
        self.view = view
        self.is_anchored = len(template) and template[-1] != '|'

    def path(self, params):
        """Build URL path fragment for this route."""
        return template2path(self.template, params, self.ranges)

    def __call__(self, request, ctx):
        """Try to dispatch a request.

        If the route matches the request URI, returns the result of calling
        resource(request), None otherwise.
        """
        path = request.path_info
        match = self.regex.match(path)
        if match:
            request._set_context(route=self)
            environ = request.environ
            match_vars = match.groupdict()
            if match_vars:
                request.routing_args[1].update(
                        dict((k, v) for k, v in match_vars.items()
                             if v is not None))
            if not self.is_anchored:
                extra_path = path[match.end():]
                script_name = request.script_name + path[:match.end()]
                environ['SCRIPT_NAME'] = script_name.encode('utf-8')
                environ['PATH_INFO'] = extra_path.encode('utf-8')
            if 'ctx' in get_args(self.resource):
                return self.resource(request, ctx=ctx)
            else:
                return self.resource(request)
        return None


class Mapper(object):
    """
    The mapper groups resources or other mappers under a common URL root, and
    dispatches incoming requests based on their URL. It also provides the WSGI
    interface for the application.

    The `ranges` parameter can be used to extend or override the default
    ranges. Ranges passed as a dictionary will be merged into the default
    ranges, with those given in `ranges` taking precedence.
    """
    default_encoding = None
    default_content_type = None

    # TODO 'root' parameter for manually specifying a URL prefix not reflected
    # in SCRIPT_NAME (e.g. when proxying).
    def __init__(self, ranges=None):
        self.ranges = DEFAULT_RANGES.copy()
        if ranges is not None:
            self.ranges.update(ranges)
        self.routes = []
        self.named_routes = {}
        self._ctx_properties = {}

    def add(self, template, resource, name=None, view=None):
        """Add a resource to the mapper under a URL template.

        The optional ``name`` assigns a name to this route that can be
        used when building URLs. The name must be unique within this
        Mapper instance.

        The optional ``view`` can be used by resources to change how to respond
        to the request based on which route it came from.
        """
        route = Route(template, resource, name=name, view=view,
                ranges=self.ranges)
        if name is not None:
            if name in self.named_routes:
                raise InvalidArgumentError("A route named '%s' already exists in this %s instance."
                        % (name, self.__class__.__name__))
            self.named_routes[name] = route
        self.routes.append(route)

    def add_ctx_property(self, name, fn, cached=True):
        if name in self._ctx_properties:
            raise InvalidArgumentError("A context property name '%s' already exists." % name)
        self._ctx_properties[name] = (fn, cached)

    def path(self, target, params):
        """Build URL path fragment for a resource or route of this mapper."""
        if type(target) in string_types:
            if '.' in target:
                # Build path for a dotted route name
                prefix, rest = target.split('.', 1)
                route = self.named_routes[prefix]
                params_copy = params.copy()
                prefix_params = {k: params_copy.pop(k) for k in route.params}
                prefix_path = route.path(prefix_params)
                next_mapper = route.resource
                return prefix_path + next_mapper.path(rest, params_copy)
            else:
                # Build path for a named route
                return self.named_routes[target].path(params)
        elif isinstance(target, Route):
            # Build path for a route instance
            for route in self.routes:
                if route is target:
                    return route.path(params)
            raise InvalidArgumentError("Route '%s' not found in this %s instance." % (target, self.__class__.__name__))
        else:
            # Build path for route resource instance
            for route in self.routes:
                if route.resource is target:
                    return route.path(params)
            raise InvalidArgumentError("No Route found for target '%s' in this %s instance." % (target, self.__class__.__name__))

    def wsgi(self, environ, start_response):
        """This methods implements the mapper's WSGI interface."""
        request = Request(environ)
        ctx = Context(request)
        try:
            response = self(request, ctx)
            response = response.conditional_to(request)
        except HTTPException as e:
            response = e.response
        except Exception:
            self.handle_error(request, sys.exc_info())
            response = InternalServerError().response
        response.add_callback(lambda: ctx._run_callbacks('close'))
        ctx._run_callbacks('finalize', request, response)
        wsgi_response = response(environ, start_response)
        ctx._run_callbacks('teardown')
        return wsgi_response

    # taken and adapted from wsgiref.handlers.BaseHandler
    def handle_error(self, request, exc_info):
        """Log the 'exc_info' tuple in the server log."""
        try:
            from traceback import print_exception
            stream = request.environ.get('wsgi.error', sys.stderr)
            print_exception(exc_info[0], exc_info[1], exc_info[2], None, stream)
            stream.flush()
        finally:
            exc_info = None  # Clear traceback to avoid circular reference

    def __call__(self, request, ctx=None):
        if ctx is None:
            ctx = Context(request=request)
        for name, (fn, cached) in self._ctx_properties.items():
            ctx.add_property(name, fn, cached=cached)
        # TODO here is were we would have to prepend self.root
        request._add_context(root=request.script_name, mapper=self, route=None)
        for route in self.routes:
            response = route(request, ctx)
            if response is not None:
                if self.default_encoding is not None:
                    response.default_encoding = self.default_encoding
                if self.default_content_type is not None:
                    response.default_content_type = self.default_content_type
                return response
        raise NotFound

    def start_server(self, host='localhost', port=9000, app=None):
        """Start a `wsgiref.simple_server` based server to run this mapper."""
        from wsgiref.simple_server import make_server
        if app is None:
            app = self.wsgi
        server = make_server(host, port, app)
        server_addr = "%s:%s" % (server.server_name, server.server_port)
        print "Server listening at http://%s/" % server_addr
        server.serve_forever()
