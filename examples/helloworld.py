from rhino import Mapper, Resource, get, ok

greeting = Resource()

@greeting.get
def hello(request):
    return ok("Hello, world!")

app = Mapper()
app.add('/', greeting)

if __name__ == '__main__':
    app.start_server()
