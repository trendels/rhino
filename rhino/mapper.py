from __future__ import absolute_import

import re
import sys
import urllib

from .errors import HTTPException, InternalServerError, NotFound
from .request import Request
from .response import Response
from .resource import Resource
from .util import call_with_ctx

__all__ = [
    'Mapper',
    'Route',
    'Context',
    'MapperException',
    'InvalidArgumentError',
    'InvalidTemplateError',
]

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
    """Convert a URL template to a regular expression.

    Converts a template, such as /{name}/ to a regular expression, e.g.
    /(?P<name>[^/]+)/ and a list of the named parameters found in the template
    (e.g. ['name']). Ranges are given after a colon in a template name to
    indicate a restriction on the characters that can appear there. For
    example, in the template::

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
    """Converts a template and a dict of parameters to a path fragment.

    Converts a template, such as /{name}/ and a dictionary of parameter
    values to a URL path (string). Parameter values will be converted to
    strings and escaped.

    Parameter values that are used are converted using `str()` and validated
    against the paremter range. Unused parameters are ignored.

    Any optional ([]) blocks in the template are skipped unless they contain at
    least one parameter and all parameters needed to fill the block (including
    nested blocks) are present in `params`.

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
        """Adds a callback to the context.

        The `phase` determines when and if the callback is executed, and which
        positional arguments are passed in:

        'enter'
            Called from :class:`Resource`, after a handler for the current
            request has been resolved, but before the handler is called.

            Arguments: request

        'leave'
            Called from :class:`Resource`, after the handler has returned
            successfully.

            Arguments: request, response

        'finalize'
            Called from :class:`Mapper`, before WSGI response is finalized.

            Arguments: request, response

        'teardown'
            Called from :class:`Mapper`, before control is passed back to the
            WSGI layer.

            Arguments: -

        'close'
            Called when the WSGI server calls `close()` on the response
            iterator.

            Arguments: -

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
    A Route links a URL template and an optional name to a resource.
    """

    def __init__(self, template, resource, ranges=None, name=None):
        if ranges is None:
            ranges = DEFAULT_RANGES
        if name is not None and any(c in name for c in './'):
            raise InvalidArgumentError("Route name '%s' contains invalid characters ('./')" % name)

        regex, params = template2regex(template, ranges)
        self.regex = re.compile(regex)
        self.params = set(params)
        self.template = template
        self.resource = resource
        self.ranges = ranges
        self.name = name
        self.is_anchored = len(template) and template[-1] != '|'

    def path(self, params):
        """Builds the URL path fragment for this route."""
        return template2path(self.template, params, self.ranges)

    def __call__(self, request, ctx):
        """Try to dispatch a request.

        Returns a the result of calling the route's target resource, or None if
        the route does not match.
        """
        path = request.path_info
        match = self.regex.match(path)
        if match:
            request._set_context(route=self)
            environ = request.environ
            match_vars = match.groupdict()
            if match_vars:
                request.routing_args.update(
                        dict((k, v) for k, v in match_vars.items()
                             if v is not None))
            if not self.is_anchored:
                extra_path = path[match.end():]
                script_name = request.script_name + path[:match.end()]
                environ['SCRIPT_NAME'] = script_name.encode('utf-8')
                environ['PATH_INFO'] = extra_path.encode('utf-8')
            return call_with_ctx(self.resource, ctx, request)
        return None


class Mapper(object):
    """
    Class variables:

    default_encoding (default ``None``):
        When set, is used to override the ``default_encoding`` of outgoing
        Responses. See :class:`Response` for details. Does not affect responses
        returned via exceptions.

    default_content_type (default ``None``):
        When set, is used to override the ``default_content_type`` of outgoing
        Responses. See :class:`Response` for details. Does not affect responses
        returned via exceptions.
    """
    default_encoding = None
    default_content_type = None

    # TODO 'root' parameter for manually specifying a URL prefix not reflected
    # in SCRIPT_NAME (e.g. when proxying).
    def __init__(self, ranges=None):
        """Create a new mapper.

        The `ranges` parameter can be used to override or augment the default
        ranges by passing in a dict mapping range names to regexp patterns.
        """
        self.ranges = DEFAULT_RANGES.copy()
        if ranges is not None:
            self.ranges.update(ranges)
        self.routes = []
        self.named_routes = {}
        self._lookup = {}  # index of routes by object ID for faster path(obj)
        self._ctx_properties = {}

    def add(self, template, resource, name=None):
        """Add a route to a resource.

        The optional `name` assigns a name to this route that can be used when
        building URLs. The name must be unique within this Mapper instance.
        """
        # Special case for standalone handler functions
        if hasattr(resource, '_rhino_meta'):
            route = Route(
                    template, Resource(resource), name=name, ranges=self.ranges)
        else:
            route = Route(
                    template, resource, name=name, ranges=self.ranges)
        obj_id = id(resource)
        if obj_id not in self._lookup:
            # It's ok to have multiple routes for the same object id.
            self._lookup[obj_id] = route
        if name is not None:
            if name in self.named_routes:
                raise InvalidArgumentError("A route named '%s' already exists in this %s instance."
                        % (name, self.__class__.__name__))
            self.named_routes[name] = route
        self.routes.append(route)

    def add_ctx_property(self, name, fn, cached=True):
        """Install a context property.

        A context property is a callable that will be called on first access of
        the property named `name` on :class:`Context` instances passing through
        this mapper. The result will be cached unless `cached` is False.

        If the context property is not callable, it will be installed
        as-is, otherwise, it will be called with the context instance as
        first argument.
        """
        if name in self._ctx_properties:
            raise InvalidArgumentError("A context property name '%s' already exists." % name)
        self._ctx_properties[name] = (fn, cached)

    def path(self, target, params):
        """Build a URL path fragment for a resource or route.

        Possible values for `target`:

        A string that does not contain a ``.``
            If the string does not contain ``.``, it will be used to look up
            a named route of this mapper instance and return it's path.

        A string of the form ``a.b``, ``a.b.c``, etc.
            Follows the route to nested mappers by splitting off consecutive
            segments. Returns the path of the route found by looking up the
            final segment on the last mapper.

        A :class:`Route` instance
            Returns the path for the route.

        A resource that was added previously
            Looks up the first route that points to this resource and
            returns its path.
        """
        if type(target) in string_types:
            if '.' in target:
                # Build path for a dotted route name
                prefix, rest = target.split('.', 1)
                route = self.named_routes[prefix]
                params_copy = params.copy()
                prefix_params = dict((k, params_copy.pop(k))
                                     for k in route.params)
                prefix_path = route.path(prefix_params)
                next_mapper = route.resource
                return prefix_path + next_mapper.path(rest, params_copy)
            else:
                # Build path for a named route
                return self.named_routes[target].path(params)
        elif isinstance(target, Route):
            # Build path for a route instance, used by for build_url('.')
            for route in self.routes:
                if route is target:
                    return route.path(params)
            raise InvalidArgumentError("Route '%s' not found in this %s instance." % (target, self.__class__.__name__))
        else:
            # Build path for route resource instance
            target_id = id(target)
            if target_id in self._lookup:
                return self._lookup[target_id].path(params)
            raise InvalidArgumentError("No Route found for target '%s' in this %s instance." % (target, self.__class__.__name__))

    def wsgi(self, environ, start_response):
        """Implements the mapper's WSGI interface."""
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
                if not isinstance(response, Response):
                    raise TypeError("Not a rhino.Response instance: %s." % response)
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
