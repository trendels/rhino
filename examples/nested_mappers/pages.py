import html
from rhino import Mapper, get

@get
def index(request):
    h = html.HTML()
    h.h1("Welcome to our website.")
    h.h2("Links")
    h.p.a("Users", href=request.url_for('/users.users'))
    return unicode(h)

app = Mapper()
app.add('/', index, 'index')
