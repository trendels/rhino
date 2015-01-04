"""
This module contains a `JinjaRenderer` class that can be used to add a
renderer property to the context that renders Jinja2 templates.

This extension requires the Jinja2 module to be installed:

    $ pip install jinja2

Example usage:

    from rhino import Mapper, get
    from rhino.ext.jinja2 import JinjaRenderer

    app = rhino.Mapper()
    app.add_ctx_property('render_template', JinjaRenderer('./templates'))

    @get
    def index(request, ctx):
        return ctx.render_template('index.html', greeting="hello, world!")

    app.add('/', index)

"""
from __future__ import absolute_import

from functools import partial

import jinja2
from rhino.response import Entity

__all__ = [
    'JinjaRenderer',
]


class JinjaRenderer(object):
    encoding = 'utf-8'
    content_type = 'text/html; charset=utf-8'

    def __init__(self, directory=None, autoescape=True, **env_args):
        if directory is not None:
            env_args['loader'] = jinja2.FileSystemLoader(directory)
        self.env = jinja2.Environment(autoescape=autoescape,  **env_args)

    def render_template(self, ctx, template_name, **values):
        template = self.env.get_template(template_name)
        body = template.render(ctx=ctx, url_for=ctx.request.url_for, **values)
        return Entity(
                body=body.encode(self.encoding),
                content_type=self.content_type)

    def __call__(self, ctx):
        return partial(self.render_template, ctx)
