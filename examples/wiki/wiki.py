from rhino import Mapper, Resource, get, redirect
import storage

wiki = storage.Storage('contents')

edit_page = Resource()
history_page = Resource()

@get
def display(request, name):
    return wiki.render_page(name)

@edit_page.get
def edit_form(request, name):
    return wiki.render_edit_form(name)

@edit_page.post
def edit(request, name):
    if request.form.get('submit'):
        wiki.store_page(name, request.form['content'])
    return redirect('/%s' % name)

@history_page.get
def history(request, name):
    return wiki.render_history_form(name)

@history_page.post
def revert(request, name):
    version = request.form.get('version')
    if request.form.get('submit') and version:
        wiki.revert_page(name, version)
    return redirect('/%s' % name)

app = Mapper(ranges={'wikiname': storage.wikiname_re.pattern})
app.default_content_type='text/html; charset=utf-8'

app.add('/', lambda req: redirect('/FrontPage'))
app.add('/{name:wikiname}', display)
app.add('/{name:wikiname}/edit', edit_page)
app.add('/{name:wikiname}/history', history_page)

if __name__ == '__main__':
    app.start_server(host='127.0.0.1', port=8080)
