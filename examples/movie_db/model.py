import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, backref

Base = declarative_base()


class Movie(Base):
    __tablename__ = 'movies'

    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String)
    rating = sa.Column(sa.Integer, default=0)

    roles = relationship('Role', backref='movie', order_by='Role.name')

    def __init__(self, title):
        self.title = title


class Actor(Base):
    __tablename__ = 'actors'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)

    roles = relationship('Role', backref='actor', order_by='Role.name')

    def __init__(self, name):
        self.name = name


class Role(Base):
    __tablename__ = 'roles'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    actor_id = sa.Column(sa.Integer, sa.ForeignKey('actors.id'))
    movie_id = sa.Column(sa.Integer, sa.ForeignKey('movies.id'))

    def __init__(self, name, actor):
        self.name = name
        self.actor = actor


def init_db(url):
    engine = sa.create_engine(url)
    Base.metadata.create_all(engine)

    session = Session(bind=engine)

    starwars = Movie("Star Wars")
    starwars.rating = 5
    starwars.roles = [
        Role("Luke Skywalker", Actor("Mark Hamill")),
        Role("Leia Organa", Actor("Carrie Fisher")),
        Role("Obi-Wan Kenobi", Actor("Sir Alec Guinness")),
        Role("Han Solo", Actor("Harrison Ford")),
    ]
    session.add(starwars)
    session.commit()
    session.close()
