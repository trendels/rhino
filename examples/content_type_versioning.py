import json

from rhino import Mapper, get

report = {
    'id': 1,
    'title': 'foo',
    'tags': ['a', 'b', 'c'],
    'date_published': '2015-01-09',
}

mime_type = 'application/vnd.acme.report+json'
mime_type_v1 = mime_type + ';v=1'
mime_type_v2 = mime_type + ';v=2'
mime_type_v3 = mime_type + ';v=3'

class report_repr(object):
    @classmethod
    def serialize(cls, report):
        obj = dict([(k, report[k]) for k in cls.fields])
        return json.dumps(obj, sort_keys=True)

class report_v1(report_repr):
    provides = mime_type_v1
    fields = ['id', 'title']

class report_v2(report_repr):
    provides = mime_type_v2
    fields = ['id', 'title', 'tags']

class report_v3(report_repr):
    provides = mime_type_v3
    fields = ['id', 'title', 'tags', 'date_published']


@get(produces=report_v1)
@get(produces=report_v2)
@get(produces=report_v3)
def get_report(request):
    return report

app = Mapper()
app.add('/', get_report)

if __name__ == '__main__':
    app.start_server()
