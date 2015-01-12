import rhino

from users import app as users_app
from pages import app as pages_app

app = rhino.Mapper()
app.default_content_type = 'text/html; charset=utf-8'

app.add('/', lambda req: rhino.redirect(req.url_for('pages.index')))
app.add('/pages|', pages_app, 'pages')
app.add('/users|', users_app, 'users')

if __name__ == '__main__':
    app.start_server()
