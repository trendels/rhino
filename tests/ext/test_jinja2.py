import jinja2
from rhino import Mapper, get
from rhino.ext.jinja2 import JinjaRenderer
from rhino.test import TestClient


def test_default_loader():
    renderer = JinjaRenderer('./templates')
    assert isinstance(renderer.env.loader, jinja2.FileSystemLoader)
    assert renderer.env.loader.searchpath == ['./templates']


def test_renderer():
    @get
    def handler(request, ctx):
        return ctx.render_template('test', foo='<script>')

    renderer = JinjaRenderer(loader=jinja2.DictLoader({'test': '{{ foo }}'}))

    app = Mapper()
    app.add_ctx_property('render_template', renderer)
    app.add('/', handler)
    client = TestClient(app.wsgi)

    res = client.get('/')
    assert res.body == '&lt;script&gt;'
    assert res.headers['Content-Type'] == 'text/html; charset=utf-8'
