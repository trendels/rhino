"""
Jinja2 support for rhino applications.

This module contains a JinjaRenderer class that can be used to add a
renderer property to the context that renders jinja2 templates.

This extension requires the Jinja2 module to be installed::

    $ pip install jinja2

Example usage::

    from rhino.ext.jinja2 import JinjaRenderer

    app = rhino.Mapper()
    app.add_ctx_property('render_template', JinjaRenderer('./templates'))

    def index(request, ctx):
        ctx.render_template('index.html', greeting="hello, world!")

    app.add('/', index)

"""
from __future__ import absolute_import

from functools import partial

import jinja2
from rhino.response import Entity


class JinjaRenderer(object):
    """Construct a property for rendering templates.

    :param str directory: The name of a directory where to look for template files.
    :param bool autoescape: Whether or not escape HTML by default (default: True)
    :param env_args: All other keyword arguments will be passed to the jinja2.Environment constructor.

    The resulting property is a callable that takes the template name as
    first argument, followed by the template variables.
    The template variables ``ctx`` and ``url_for`` will be provided by default
    to all templates.
    """
    #: Encoding to use for the entity body.
    encoding = 'utf-8'
    #: Value for the Content-Type entity header.
    content_type = 'text/html; charset=utf-8'

    def __init__(self, directory=None, autoescape=True, **env_args):
        if directory is not None:
            env_args['loader'] = jinja2.FileSystemLoader(directory)
        #: The jinja2.Environment instance. Can be used to add additional
        #: filters after initalization
        self.env = jinja2.Environment(autoescape=autoescape,  **env_args)

    def render_template(self, ctx, template_name, **values):
        template = self.env.get_template(template_name)
        body = template.render(ctx=ctx, url_for=ctx.request.url_for, **values)
        return Entity(
                body=body.encode(self.encoding),
                content_type=self.content_type)

    def __call__(self, ctx):
        return partial(self.render_template, ctx)
