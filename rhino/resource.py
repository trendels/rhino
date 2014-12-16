from __future__ import absolute_import

import functools
from collections import defaultdict, namedtuple

from .errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from .response import Response
from .util import dual_use_decorator, dual_use_decorator_method
from .vendor import mimeparse

request_handler = namedtuple('request_handler', 'fn verb view accepts provides')
MIMEPARSE_NO_MATCH = (-1, 0)


def _make_handler_decorator(verb, view=None, accepts='*/*', provides=None):
    def decorator(fn):
        handler = request_handler(fn, verb, view, accepts, provides)
        @functools.wraps(fn)
        def wrapper(request):
            return dispatch_request(request, {view: {verb: [handler]}})
        return wrapper
    return decorator


@dual_use_decorator
def get(*args, **kw):
    """Create a resource from a standalone handler.

    Handles GET requests."""
    return _make_handler_decorator('GET', *args, **kw)


@dual_use_decorator
def post(*args, **kw):
    """Create a resource from a standalone handler.

    Handles POST requests."""
    return _make_handler_decorator('POST', *args, **kw)


@dual_use_decorator
def put(*args, **kw):
    """Create a resource from a standalone handler.

    Handles PUT requests."""
    return _make_handler_decorator('PUT', *args, **kw)


@dual_use_decorator
def delete(*args, **kw):
    """Create a resource from a standalone handler.

    Handles DELETE requests."""
    return _make_handler_decorator('DELETE', *args, **kw)


@dual_use_decorator
def patch(*args, **kw):
    """Create a resource from a standalone handler.

    Handles PATCH requests."""
    return _make_handler_decorator('PATCH', *args, **kw)


@dual_use_decorator
def options(*args, **kw):
    """Create a resource from a standalone handler.

    Handles OPTIONS requests."""
    return _make_handler_decorator('OPTIONS', *args, **kw)


def make_response(obj):
    """
    Coerces the value returned from a request handler into a Response instance.
    """
    if obj is None:
        raise TypeError("Handler return value cannot be None.")
    if isinstance(obj, Response):
        return obj
    return Response(200, body=obj)


def dispatch_request(request, view_handlers, wrapper=None):
    view = None
    if request._context:  # Allow context to be missing for easier testing
        view = request._context[-1].route.view

    if view not in view_handlers:
        raise NotFound

    method_handlers = view_handlers[view]

    verb = request.method.upper()
    if verb not in method_handlers:
        if verb == 'HEAD' and 'GET' in method_handlers:
            verb = 'GET'
        else:
            allowed_methods = set(method_handlers.keys())
            if 'HEAD' not in allowed_methods and 'GET' in allowed_methods:
                allowed_methods.add('HEAD')
            allowed_methods.add('OPTIONS')
            allow = ', '.join(sorted(allowed_methods))
            if verb == 'OPTIONS':
                return Response(200, headers=[('Allow', allow)])
            else:
                raise MethodNotAllowed(allow=allow)

    handlers = method_handlers[verb]
    can_vary = any(h for h in handlers if h.provides is not None)

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

    handler = handlers[0]
    args, kw = request.routing_args
    fn = wrapper(handler.fn) if wrapper else handler.fn
    response = make_response(fn(request, *args, **kw))

    if handler.provides:
        response.headers.setdefault('Content-Type', handler.provides)

    if can_vary:
        vary_header = response.headers.get('Vary', '')
        vary = set(filter(None, [s.strip() for s in vary_header.split(',')]))
        vary.add('Accept')
        response.headers['Vary'] = ', '.join(sorted(vary))

    return response


def negotiate_content_type(content_type, handlers):
    """Of all media-ranges acceped by handlers, find the most specific one that
    matches content_type, and return only those handlers that accept it.
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
    provided = [h.provides for h in handlers]
    if None not in provided:
        # All handlers are annotated with the mime-type they
        # provide: find the best match.
        #
        # mimeparse.best_match expects the supported mime-types to be sorted
        # in order of increasing desirability. By default, we use the order in
        # which handlers were added (earlier means better).
        # TODO: add "priority" parameter for user-defined priorities.
        best_match = mimeparse.best_match(reversed(provided), accept)
        return [h for h in handlers if h.provides == best_match]
    else:
        # Not all handlers are annotated - disable content-negotiation
        # for Accept.
        # TODO: Enable "Optimistic mode": If a fully qualified mime-type was
        # requested and we have a specific handler it, return that instead of
        # the default handler (depending on 'q' value).
        return [h for h in handlers if h.provides is None]


class Resource():
    def __init__(self):
        self._handlers = defaultdict(lambda: defaultdict(list))
        self._wrapper = None

    def __call__(self, request):
        return dispatch_request(request, self._handlers, wrapper=self._wrapper)

    def _make_decorator(self, verb, view=None, accepts='*/*', provides=None):
        def decorator(fn):
            handler = request_handler(fn, verb, view, accepts, provides)
            self._handlers[view][verb].append(handler)
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
        def wrapper(handler):
            def wrapped(request, *args, **kw):
                new_kw = fn(request, *args, **kw)
                return handler(request, *args, **new_kw)
            return _wrapper
        self._wrapper = wrapper
        return fn
