import json

from rhino import Mapper, get

# Our internal representation
report = {
    'title': 'foo',
    'author': 'Fred',
    'date': '2015-01-09',
    'tags': ['a', 'b', 'c'],
}

# Base class for our representations
class report_repr(object):
    @classmethod
    def serialize(cls, report):
        obj = dict([(k, report[k]) for k in cls.fields])
        return json.dumps(obj, sort_keys=True)

# Different versions of the representation
class report_v1(report_repr):
    provides = 'application/vnd.acme.report+json;v=1'
    fields = ['title', 'author']

class report_v2(report_repr):
    provides = 'application/vnd.acme.report+json;v=2'
    fields = ['title', 'author', 'date']

class report_v3(report_repr):
    provides = 'application/vnd.acme.report+json;v=3'
    fields = ['title', 'author', 'date', 'tags']


# One handler can handle multiple representations.
# Here, report_v3 is the default when the client doesn't specify a preference.
@get(produces=report_v1)
@get(produces=report_v2)
@get(produces=report_v3)
def get_report(request):
    return report

app = Mapper()
app.add('/', get_report)

if __name__ == '__main__':
    app.start_server()
