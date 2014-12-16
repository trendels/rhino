from rhino import Mapper, get, ok

@get
def hello(request):
    return ok("Hello, world!")

app = Mapper()
app.add('/', hello)

if __name__ == '__main__':
    app.start_server()
