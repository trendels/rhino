import json
from cgi import escape

from rhino import Mapper, Resource, ok
from rhino.errors import BadRequest

greeting = Resource()
greeting.text = "Hello, world!"

@greeting.get(provides='text/html')
def get_html(request, ctx):
    return '<html><h1>%s</h1></html>' % escape(greeting.text)

@greeting.get(provides='application/json')
def get_json(request, ctx):
    return json.dumps({'greeting': greeting.text})

@greeting.put(accepts='application/json')
def put_json(request, ctx):
    try:
        data = json.loads(request.body)
        greeting.text = data['greeting']
    except Exception:
        raise BadRequest
    return ok()

app = Mapper()
app.add('/', greeting)

if __name__ == '__main__':
    app.start_server()
