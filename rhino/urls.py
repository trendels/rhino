from __future__ import absolute_import

from collections import namedtuple

request_context = namedtuple('request_context', 'root mapper route')
string_types = (str, unicode)


def build_url(context, target, args=None, kw=None):
    if not context:  # pragma: no cover
        raise RuntimeError("No routing context present.")
    if args is None:
        args = []
    if kw is None:
        kw = {}
    if type(target) in string_types and len(target) \
            and (target[0] == '/' or '.' in target):
        # Build URL for a relative or absolute route name
        if target == '.':  # The current route
            c = context[-1]
            return c.root + c.mapper.path(c.route, args, kw)
        elif target == '/':  # The root mapper instance
            return context[0].root or '/'
        elif target[0] == '/':  # A dotted route name anchored at the root
            c = context[0]
            return c.root + c.mapper.path(target[1:], args, kw)
        else:  # A route name relative to the current mapper
            rel_name = target.lstrip('.')
            leading_dots = target[:-len(rel_name)]
            c = context[-len(leading_dots)]
            return c.root + c.mapper.path(rel_name, args, kw)
    else:
        # Try resolving the target via the current mapper
        c = context[-1]
        return c.root + c.mapper.path(target, args, kw)
