import json

from rhino import Mapper, Resource, ok
from rhino.errors import BadRequest

# Helper function to parse JSON from a file-like object.
# Raises BadRequest if the content is not valid JSON.
def read_json(f):
    try:
        obj = json.load(f)
    except ValueError as e:
        raise BadRequest("Invalid JSON: %s" % e)
    return obj

# Example wrapper that automatically parses Request.body as JSON if the request
# has an 'application/json' Content-Type, and also serializes dicts, lists and
# tuples returned from handlers as json.
def json_api_wrapper(app):
    def wrap(request, ctx):
        if request.content_type == 'application/json':
            request._body_reader = read_json
        response = app(request, ctx)
        if isinstance(response.body, (dict, list, tuple)):
            response.body = json.dumps(response.body)
            response.headers['Content-Type'] = 'application/json'
        return response
    return wrap


data = {'message': 'hello, world!'}

data_resource = Resource()

@data_resource.get
def get_data(request):
    return data

@data_resource.put
def update_data(request):
    data['message'] = request.body['message']
    return data

app = Mapper()
app.add_wrapper(json_api_wrapper)
app.add('/', data_resource)

if __name__ == '__main__':
    app.start_server()
