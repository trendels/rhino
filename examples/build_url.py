from collections import namedtuple

from rhino import Mapper, Resource, redirect
from rhino.errors import NotFound

USERS, PAGES = {}, {}

class User(namedtuple('User', 'id name page_ids')):
    @property
    def pages(self):
        return dict((page_id, PAGES[page_id]) for page_id in self.page_ids)

class Page(namedtuple('Page', 'id title text user_id')):
    @property
    def user(self):
        return USERS[self.user_id]


USERS[1] = User(1, 'fred', [1])
PAGES[1] = Page(1, 'hello', 'hello, world!', 1)


page_details = Resource()

# Implement fetching page from url parameters
@page_details.from_url
def fetch_page(req, user_id, page_id):
    user = USERS.get(int(user_id))
    if user:
        page = user.pages.get(int(page_id))
    if not page:
        raise NotFound('Page not found')
    return {'page': page}

# Override how URLs for this resource are built: require one argument,
# 'page' and translate to user_id + page_id.
@page_details.make_url
def page_url(url, page):
    return url(user_id=page.user.id, page_id=page.id)

# This is was the `Resource.make_url` decorator does under the hood:
#page_details.build_url = page_url

@page_details.get
def get_page(req, page):
    page_url = req.url_for(page_details, page)
    return "The url for this page is %s" % page_url


app = Mapper()
app.add('/', lambda req: redirect(req.url_for('page', PAGES[1])))
app.add('/u:{user_id:digits}/p:{page_id:digits}', page_details, 'page')

if __name__ == '__main__':
    app.start_server()
