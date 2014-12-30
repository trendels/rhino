import os

from rhino import Mapper, StaticFile, StaticDirectory, get
from rhino.errors import NotFound
from rhino.ext.jinja2 import JinjaRenderer
from rhino.ext.sqlalchemy import SessionProperty

from model import Movie, Actor

APP_ROOT = os.path.dirname(__file__)


@get
def index(request, ctx):
    movies = ctx.db.query(Movie).order_by(Movie.title.asc())
    return ctx.render_template('index.html', movies=movies)


@get
def show_movie(request, ctx, id):
    movie = ctx.db.query(Movie).get(int(id))
    if not movie:
        raise NotFound
    return ctx.render_template('movie.html', movie=movie)


@get
def show_actor(request, ctx, id):
    actor = ctx.db.query(Actor).get(int(id))
    if not actor:
        raise NotFound
    return ctx.render_template('actor.html', actor=actor)


def get_app(db_url):
    app = Mapper()

    template_dir = os.path.join(APP_ROOT, 'templates')
    static_dir = os.path.join(APP_ROOT, 'static')
    favicon = os.path.join(static_dir, 'favicon.ico')

    app.add_ctx_property('db', SessionProperty(db_url))
    app.add_ctx_property('render_template', JinjaRenderer(template_dir))

    app.add('/', index)
    app.add('/movies/{id}', show_movie, name='movie')
    app.add('/actors/{id}', show_actor, name='actor')
    app.add('/favicon.ico', StaticFile(favicon))
    app.add('/static/{path:any}', StaticDirectory(static_dir), name='static')
    return app

if __name__ == '__main__':
    import os
    from model import init_db

    if not os.path.exists('movies.db'):
        init_db('sqlite:///movies.db')

    app = get_app('sqlite:///movies.db')
    app.start_server()
