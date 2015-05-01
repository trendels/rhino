from __future__ import absolute_import

import types
from collections import defaultdict, namedtuple

from .errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from .response import Response
from .util import dual_use_decorator, dual_use_decorator_method, call_with_ctx
from .vendor import mimeparse

__all__ = [
    'Resource',
    'make_response',
    'get', 'post', 'put', 'delete', 'patch', 'options',
]

class_types = (type, types.ClassType)  # new-style and old-style classes

VIEW_SEPARATOR = ':'
MIMEPARSE_NO_MATCH = (-1, 0)


class handler_metadata(namedtuple(
        'handler_metadata', 'verb view accepts provides produces consumes')):
    @classmethod
    def create(cls, verb, view=None, accepts=None, provides=None,
                consumes=None, produces=None):
        if (accepts and consumes):
            raise ValueError("accepts and consumes are mutually exclusive")
        if (provides and produces):
            raise ValueError("provides and produces are mutually exclusive")
        if consumes:
            accepts = consumes.accepts
        if produces:
            provides = produces.provides
        if accepts is None:
            accepts = '*/*'
        if view and VIEW_SEPARATOR in view:
            raise ValueError("View name cannot contain '%s': %s"
                    % (VIEW_SEPARATOR, view))
        return cls(verb, view, accepts, provides, produces, consumes)


def _make_handler_decorator(*args, **kw):
    def decorator(fn):
        if not hasattr(fn, '_rhino_meta'):
            fn._rhino_meta = []
        fn._rhino_meta.append(handler_metadata.create(*args, **kw))
        return fn
    return decorator


@dual_use_decorator
def get(*args, **kw):
    """Mark the decorated function as a handler for GET requests."""
    return _make_handler_decorator('GET', *args, **kw)


@dual_use_decorator
def post(*args, **kw):
    """Mark the decorated function as a handler for POST requests."""
    return _make_handler_decorator('POST', *args, **kw)


@dual_use_decorator
def put(*args, **kw):
    """Mark the decorated function as a handler for PUT requests."""
    return _make_handler_decorator('PUT', *args, **kw)


@dual_use_decorator
def delete(*args, **kw):
    """Mark the decorated function as a handler for DELETE requests."""
    return _make_handler_decorator('DELETE', *args, **kw)


@dual_use_decorator
def patch(*args, **kw):
    """Mark the decorated function as a handler for PATCH requests."""
    return _make_handler_decorator('PATCH', *args, **kw)


@dual_use_decorator
def options(*args, **kw):
    """Mark the decorated function as a handler for OPTIONS requests."""
    return _make_handler_decorator('OPTIONS', *args, **kw)


def make_response(obj):
    """Try to coerce an object into a Response instance."""
    if obj is None:
        raise TypeError("Handler return value cannot be None.")
    if isinstance(obj, Response):
        return obj
    return Response(200, body=obj)


def resolve_handler(request, view_handlers):
    """Select a suitable handler to handle the request.

    Returns a (handler, vary) tuple, where handler is a handler_metadata tuple
    and vary is a set containing header names that were used during content
    negotiation and that should be included in the 'Vary' header of the
    outgoing response.

    When no suitable handler exists, raises NotFound, MethodNotAllowed,
    UnsupportedMediaType or NotAcceptable.
    """
    view = None
    if request._context:  # Allow context to be missing for easier testing
        route_name = request._context[-1].route.name
        if route_name and VIEW_SEPARATOR in route_name:
            view = route_name.split(VIEW_SEPARATOR, 1)[1] or None

    if view not in view_handlers:
        raise NotFound

    method_handlers = view_handlers[view]

    verb = request.method
    if verb not in method_handlers:
        if verb == 'HEAD' and 'GET' in method_handlers:
            verb = 'GET'
        else:
            allowed_methods = set(method_handlers.keys())
            if 'HEAD' not in allowed_methods and 'GET' in allowed_methods:
                allowed_methods.add('HEAD')
            allow = ', '.join(sorted(allowed_methods))
            raise MethodNotAllowed(allow=allow)

    handlers = method_handlers[verb]
    vary = set()
    if len(set(h.provides for h in handlers if h.provides is not None)) > 1:
        vary.add('Accept')
    if len(set(h.accepts for h in handlers)) > 1:
        vary.add('Content-Type')

    content_type = request.content_type
    if content_type:
        handlers = negotiate_content_type(content_type, handlers)
        if not handlers:
            raise UnsupportedMediaType

    accept = request.headers.get('Accept')
    if accept:
        handlers = negotiate_accept(accept, handlers)
        if not handlers:
            raise NotAcceptable

    return handlers[0], vary


def negotiate_content_type(content_type, handlers):
    """Filter handlers that accept a given content-type.

    Finds the most specific media-range that matches `content_type`, and
    returns those handlers that accept it.
    """
    accepted = [h.accepts for h in handlers]
    scored_ranges = [(mimeparse.fitness_and_quality_parsed(content_type,
        [mimeparse.parse_media_range(mr)]), mr) for mr in accepted]

    # Sort by fitness, then quality parsed (higher is better)
    scored_ranges.sort(reverse=True)
    best_score = scored_ranges[0][0]  # (fitness, quality)
    if best_score == MIMEPARSE_NO_MATCH or not best_score[1]:
        return []

    media_ranges = [pair[1] for pair in scored_ranges if pair[0] == best_score]
    best_range = media_ranges[0]
    return [h for h in handlers if h.accepts == best_range]


def negotiate_accept(accept, handlers):
    """Filter handlers that provide an acceptable mime-type.

    Finds the best match among handlers given an Accept header, and returns
    those handlers that provide the matching mime-type.
    """
    provided = [h.provides for h in handlers]
    if None in provided:
        # Not all handlers are annotated - disable content-negotiation
        # for Accept.
        # TODO: We could implement an "optimistic mode": If a fully qualified
        # mime-type was requested and we have a specific handler that provides
        # it, choose that handler instead of the default handler (depending on
        # 'q' value).
        return [h for h in handlers if h.provides is None]
    else:
        # All handlers are annotated with the mime-type they
        # provide: find the best match.
        #
        # mimeparse.best_match expects the supported mime-types to be sorted
        # in order of increasing desirability. By default, we use the order in
        # which handlers were added (earlier means better).
        # TODO: add "priority" parameter for user-defined priorities.
        best_match = mimeparse.best_match(reversed(provided), accept)
        return [h for h in handlers if h.provides == best_match]


class Resource(object):
    """
    Represents a REST resource.

    This class can be used in multiple ways:

    As a standalone resource, using it's methods to register handlers:

        my_resource = Resource()

        @my_resource.get
        def get_resource(request):
            # ...

    As a class decorator for class-based resources:

        @Resource
        class MyResource(object):
            @get
            def index(self, request):
                # ...

    As a wrapper to create resouces from custom objects:

        class MyClass(object):
            def __init_(self, *args):
                # ...

            @get
            def index(self, request):
                # ...

        my_resource = Resource(MyClass())

    When used as a wrapper or class decorator, handlers will be picked up from
    methods of the wrapped instance or class that have been decorated with one
    of the decorator functions provided by this module (`get`, `post`, etc.)

    Additionally, if the wrapped object implements `from_url`, that method will
    be called before any handler to filter the URL parameters that will be
    passed to the handler as keyword arguments.

    When used as a standalone instance, functions can be registered as handlers
    using the instance's methods, as shown above. The `from_url` method can be
    used in the same way to register a filter for URL parameters.
    """

    def __init__(self, wrapped=None):
        self._wrapped = wrapped
        self._handlers = defaultdict(lambda: defaultdict(list))
        self._handler_lookup = {}
        self._from_url = None
        if wrapped is not None:
            if hasattr(wrapped, '_rhino_meta'):
                for meta in wrapped._rhino_meta:
                    self._handlers[meta.view][meta.verb].append(meta)
                    self._handler_lookup[meta] = wrapped
            else:
                for name in dir(wrapped):
                    prop = getattr(wrapped, name)
                    if hasattr(prop, '_rhino_meta'):
                        for meta in prop._rhino_meta:
                            self._handlers[meta.view][meta.verb].append(meta)
                            self._handler_lookup[meta] = prop

    def __call__(self, request, ctx):
        resource_is_class = type(self._wrapped) in class_types
        resource = self._wrapped() if resource_is_class else self._wrapped
        try:
            handler, vary = resolve_handler(request, self._handlers)
        except MethodNotAllowed as e:
            # Handle 'OPTIONS' requests by default
            allow = e.response.headers.get('Allow', '')
            allowed_methods = set([s.strip() for s in allow.split(',')])
            allowed_methods.add('OPTIONS')
            allow = ', '.join(sorted(allowed_methods))
            if request.method == 'OPTIONS':
                return Response(200, headers=[('Allow', allow)])
            else:
                e.response.headers['Allow'] = allow
                raise

        if handler.consumes:
            reader = handler.consumes.deserialize
            request._body_reader = lambda f: call_with_ctx(reader, ctx, f)

        ctx._run_callbacks('enter', request)

        url_args_filter = self._from_url or getattr(resource, 'from_url', None)
        kw = request.routing_args
        if url_args_filter:
            kw = call_with_ctx(url_args_filter, ctx, request, **kw)

        fn = self._handler_lookup[handler]
        if resource_is_class:
            rv = call_with_ctx(fn, ctx, resource, request, **kw)
        else:
            rv = call_with_ctx(fn, ctx, request, **kw)
        response = make_response(rv)

        ctx._run_callbacks('leave', request, response)

        if handler.produces:
            writer = handler.produces.serialize
            response.body = call_with_ctx(writer, ctx, response.body)

        if handler.provides:
            response.headers.setdefault('Content-Type', handler.provides)

        if vary:
            vary_header = response.headers.get('Vary', '')
            vary_items = set(filter(
                None, [s.strip() for s in vary_header.split(',')]))
            vary_items.update(vary)
            response.headers['Vary'] = ', '.join(sorted(vary_items))
        return response

    def _make_decorator(self, *args, **kw):
        def decorator(fn):
            meta = handler_metadata.create(*args, **kw)
            self._handlers[meta.view][meta.verb].append(meta)
            self._handler_lookup[meta] = fn
            return fn
        return decorator

    @dual_use_decorator_method
    def get(self, *args, **kw):
        """Install the decorated function as a handler for GET requests."""
        return self._make_decorator('GET', *args, **kw)

    @dual_use_decorator_method
    def post(self, *args, **kw):
        """Install the decorated function as a handler for POST requests."""
        return self._make_decorator('POST', *args, **kw)

    @dual_use_decorator_method
    def put(self, *args, **kw):
        """Install the decorated function as a handler for PUT requests."""
        return self._make_decorator('PUT', *args, **kw)

    @dual_use_decorator_method
    def delete(self, *args, **kw):
        """Install the decorated function as a handler for DELETE requests."""
        return self._make_decorator('DELETE', *args, **kw)

    @dual_use_decorator_method
    def patch(self, *args, **kw):
        """Install the decorated function as a handler for PATCH requests."""
        return self._make_decorator('PATCH', *args, **kw)

    @dual_use_decorator_method
    def options(self, *args, **kw):
        """Install the decorated function as a handler for OPTIONS requests."""
        return self._make_decorator('OPTIONS', *args, **kw)

    def from_url(self, fn):
        """Install the decorated function as a filter for URL parameters."""
        self._from_url = fn
        return fn

    def make_url(self, fn):
        """Install the decorated function as the 'build_url' attribute."""
        self.build_url = fn
        return fn
