from rhino import Mapper, Resource, StaticDirectory, get, post, redirect
from rhino.ext.jinja2 import JinjaRenderer

import model
import service
from service import get_item_from_url


@get
def index(request, ctx, error=None):
    items = model.all_items()
    return ctx.render_template('index.html', items=items, error=error)


@post
def add_item(request, ctx):
    text = request.form['text'].strip()
    if not text:
        return index(request, ctx, error="Item text can not be empty")
    item = model.add_item(text)
    return redirect(request.url_for('index'))


item_details = Resource()
item_details.from_url(get_item_from_url)


@item_details.get('edit')
def edit_item_form(request, ctx, item, error=None):
    return ctx.render_template('edit_todo.html', item=item, error=error)


@item_details.post('edit')
def edit_item(request, ctx, item):
    print request.form.items()
    text = request.form['text'].strip()
    done = request.form.get('done') == 'done'
    if not text:
        return edit_item_form(
                request, ctx, item, error="Item text can not be empty")
    new_item = model.update_item(item.id, text=text, done=done)
    return redirect(request.url_for('index'))


@item_details.get('delete')
def delete_item_form(request, ctx, item):
    return ctx.render_template('delete_todo.html', item=item)


@item_details.post('delete')
def delete_item(request, item):
    model.delete_item(item.id)
    return redirect(request.url_for('index'))


app = Mapper()
app.add_ctx_property('render_template', JinjaRenderer('./templates'))

app.add('/', index, 'index')
app.add('/add', add_item, 'add_item')
app.add('/item/{item_id:digits}/edit', item_details, 'item:edit')
app.add('/item/{item_id:digits}/delete', item_details, 'item:delete')
app.add('/static/{path:any}', StaticDirectory('./static'), 'static')
app.add('/api|', service.app, 'api')

if __name__ == '__main__':
   app.start_server()
