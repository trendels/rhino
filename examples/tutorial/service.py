import json
from hashlib import md5

from rhino import Mapper, Resource, ok, created, no_content
from rhino.errors import BadRequest, NotFound

import model

todo_list = Resource()
todo_item = Resource()

_md5 = lambda s: md5(s.encode('utf-8')).hexdigest()


def serialize_item(request, item):
    return {
        'text': item.text,
        'done': item.done,
        'href': request.url_for(todo_item, item_id=item.id),
    }


@todo_list.get(provides='text/plain')
def list_todos_text(request):
    return '\n'.join([item.text for item in model.all_items()])


@todo_item.get(provides='text/plain')
def get_item_text(request, item):
    return item.text


@todo_list.get(provides='application/json')
def list_todos_json(request):
    todos = [serialize_item(request, item) for item in model.all_items()]
    data = json.dumps(todos)
    return ok(data, etag=_md5(data))


@todo_list.post(accepts='application/json')
def add_todo_json(request):
    try:
        data = json.loads(request.body)
        item = model.add_item(data['text'])
    except Exception:
        raise BadRequest
    return created(location=request.url_for(todo_item, item_id=item.id))


@todo_item.from_url
def get_item_from_url(request, item_id):
    item = model.get_item(int(item_id))
    if not item:
        raise NotFound
    return {'item': item}


@todo_item.get(provides='application/json')
def get_item_json(request, item):
    data = jsond.umps(serialize_item(request, item))
    return ok(json.dumps(data), etag=_md5_etag)


@todo_item.put(accepts='application/json', provides='application/json')
def update_item_json(request, item):
    try:
        data = json.loads(request.body)
        new_item = model.update_item(item.id, data['text'], data['done'])
    except Exception as e:
        raise BadRequest(str(e))
    data = serialize_item(request, new_item)
    return ok(data, etag=_md5(data))


@todo_item.delete
def delete_item(request, item):
    model.delete_item(item.id)
    return no_content()


app = Mapper()
app.add('/todos', todo_list)
app.add('/todos/{item_id:digits}', todo_item)

if __name__ == '__main__':
    app.start_server()
