import html
from rhino import Mapper, get
from rhino.errors import NotFound

users = ['mia', 'fred', 'doge']

@get
def list_users(request):
    h = html.HTML()
    h.h1('Users')
    ul = h.ul()
    for name in users:
        ul.li.a(name, href=request.url_for('user', name))
    return unicode(h)

@get
def show_user(request, name):
    if name not in users:
        raise NotFound
    h = html.HTML()
    h.h1(name.title())
    h.p("Welcome to %s's page." % name)
    h.hr
    h.a("Home", href=request.url_for('/'))
    return unicode(h)

app = Mapper()
app.add('/', list_users, 'users')
app.add('/{name:alnum}', show_user, 'user')
