import jinja2
from rhino.mapper import Context
from rhino.request import Request
from rhino.ext.jinja2 import JinjaRenderer
from rhino.test import TestClient


def test_default_loader():
    renderer = JinjaRenderer('./templates')
    assert isinstance(renderer.env.loader, jinja2.FileSystemLoader)
    assert renderer.env.loader.searchpath == ['./templates']


def test_renderer():
    renderer = JinjaRenderer(loader=jinja2.DictLoader({'test': '{{ foo }}'}))
    ctx = Context()
    ctx.request = Request({})
    ctx.add_property('render_template', renderer)
    entity = ctx.render_template('test', foo='<script>')
    assert entity.body == '&lt;script&gt;'
    assert entity.headers['Content-Type'] == 'text/html; charset=utf-8'
