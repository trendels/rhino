from collections import namedtuple
from itertools import count

TodoItem = namedtuple('TodoItem', 'id text done')

TODOS = {
    0: TodoItem(0, "Do the Rhino tutorial", True),
    1: TodoItem(1, "Learn about RESTful web services", False),
    2: TodoItem(2, "???", False),
    3: TodoItem(3, "Profit!", False),
}

_todo_id = count(len(TODOS))

def all_items():
    return [TODOS.get(id) for id in sorted(TODOS.keys())]

def get_item(id):
    return TODOS.get(id)

def add_item(text, done=False):
    item = TodoItem(next(_todo_id), text, done)
    TODOS[item.id] = item
    return item

def update_item(id, text, done):
    TODOS[id] = TODOS[id]._replace(text=text, done=done)
    return TODOS[id]

def delete_item(id):
    del TODOS[id]
