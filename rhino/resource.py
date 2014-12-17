from __future__ import absolute_import

import types
from collections import defaultdict, namedtuple

from .errors import NotFound, MethodNotAllowed, UnsupportedMediaType, \
        NotAcceptable
from .response import Response
from .util import dual_use_decorator, dual_use_decorator_method, get_args
from .vendor import mimeparse

request_handler = namedtuple('request_handler', 'name verb view accepts provides')
class_types = (type, types.ClassType)  # new-style and old-style classes
MIMEPARSE_NO_MATCH = (-1, 0)


def _add_handler_metadata(fn, verb, view=None, accepts='*/*', provides=None):
    if hasattr(fn, '_rhino_meta'):
        raise AttributeError("Decorated function already has a '_rhino_meta' attribute: %s" % fn._rhino_meta)
    meta = request_handler(fn.__name__, verb, view, accepts, provides)
    fn._rhino_meta = meta


def _make_handler_decorator(*args, **kw):
    def decorator(fn):
        _add_handler_metadata(fn, *args, **kw)
        return fn
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


def resolve_handler(request, view_handlers):
    """Select a suitable handler to handle the request.

    Returns a tuple of (handler, vary), where handler is a request_handler
    tuple and vary is a set containing header names that were used during
    content-negotiation and that have to be included in the 'Vary' header of
    the outgoing response.

    When no suitable handler exists, raises NotFound, MethodNotAllowed,
    UnsupportedMediaType or NotAcceptable.
    """
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
            allow = ', '.join(sorted(allowed_methods))
            raise MethodNotAllowed(allow=allow)

    handlers = method_handlers[verb]
    vary = set()
    if len(set(h.provides for h in handlers if h.provides is not None)) > 1:
        vary.add('Accept')
    if len(set(h.accepts for h in handlers if h.accepts != '*/*')) > 1:
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

    handler = handlers[0]
    return handler, vary


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


class ResourceWrapper(object):
    def __init__(self, resource):
        self.resource = resource
        self.resource_is_handler = False
        self.handlers = defaultdict(lambda: defaultdict(list))
        if hasattr(resource, '_rhino_meta'):
            meta = resource._rhino_meta
            self.handlers[meta.view][meta.verb].append(meta)
            self.resource_is_handler = True
        else:
            for name in dir(resource):
                prop = getattr(resource, name)
                if hasattr(prop, '_rhino_meta'):
                    # Make sure we store the actual property name which we can
                    # use to retrieve it from the instance again later.
                    # TODO we could also store a reference to the function
                    # in the handler metadata, instead of looking it up later.
                    meta = prop._rhino_meta._replace(name=name)
                    self.handlers[meta.view][meta.verb].append(meta)

    def __call__(self, request, ctx):
        resource = self.resource
        if not self.handlers:
            if 'ctx' in get_args(resource):
                response = resource(request, ctx)
            else:
                response = resource(request)
            if response is None:
                raise NotFound
            if not isinstance(response, Response):
                raise TypeError("Calling resource '%s' returned '%s' which is not None or an instance of rhino.Response" % (resource, response))
            return response
        else:
            try:
                handler, vary = resolve_handler(request, self.handlers)
            except MethodNotAllowed as e:
                # Handle 'OPTIONS' requests by default
                allow = e.response.headers.get('Allow', '')
                allowed_methods = set([s.strip() for s in allow.split(',')])
                allowed_methods.add('OPTIONS')
                allow = ', '.join(sorted(allowed_methods))
                if request.method.upper() == 'OPTIONS':
                    return Response(200, headers=[('Allow', allow)])
                else:
                    e.response.headers['Allow'] = allow
                    raise

            if isinstance(resource, class_types):
                resource = resource()
            if not self.resource_is_handler:
                if callable(resource):
                    # TODO we could allow the resource to return a Response
                    # instance here as a shortcut to abort further processing.
                    if 'ctx' in get_args(resource):
                        rv = resource(request, ctx)
                    else:
                        rv = resource(request)
                    if rv is not None:
                        raise ValueError("Calling '%s' for initialization returned a value: '%s'" % (resource, rv))
            request._run_callbacks('enter', request)
            args, kw = request.routing_args
            if self.resource_is_handler:
                fn = resource
            else:
                fn = getattr(resource, handler.name)
            if 'ctx' in get_args(fn):
                response = make_response(fn(request, ctx, *args, **kw))
            else:
                response = make_response(fn(request, *args, **kw))
            request._run_callbacks('leave', request, response)

            if handler.provides:
                response.headers.setdefault('Content-Type', handler.provides)

            if vary:
                vary_header = response.headers.get('Vary', '')
                vary_items = set(filter(
                    None, [s.strip() for s in vary_header.split(',')]))
                vary_items.update(vary)
                response.headers['Vary'] = ', '.join(sorted(vary_items))
            return response


class Resource(object):
    def __init__(self):
        self._from_url = None

    def __call__(self, request, ctx):
        if self._from_url:
            args, kw = request.routing_args
            if 'ctx' in get_args(self._from_url):
                kw = self._from_url(request, ctx, *args, **kw)
            else:
                kw = self._from_url(request, *args, **kw)
            request.routing_args[1].clear()
            request.routing_args[1].update(kw)

    def _make_decorator(self, *args, **kw):
        def decorator(fn):
            name = fn.__name__
            if hasattr(self, name):
                raise AttributeError("A property named '%s' already exists on this '%s' instance." % (name, self.__class__.__name__))
            _add_handler_metadata(fn, *args, **kw)
            setattr(self, name, fn)
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
        self._from_url = fn
        return fn
