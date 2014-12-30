from datetime import datetime, timedelta

from pytest import raises as assert_raises
from rhino.http import datetime_to_httpdate, match_etag, total_seconds, \
        cache_control


def test_datetime_to_httpdate():
    assert datetime_to_httpdate(1) == 'Thu, 01 Jan 1970 00:00:01 GMT'
    assert datetime_to_httpdate(datetime(1970, 1, 2)) == 'Fri, 02 Jan 1970 00:00:00 GMT'


def test_match_etag():
    assert not match_etag(None, '*')
    assert not match_etag(None, '"abc"')
    assert not match_etag(None, '"abc"', weak=True)
    assert not match_etag('"abc"', '"def"')
    assert not match_etag('"abc"', '"def", w/"abc"')

    assert match_etag('"abc"', '"def", w/"abc"', weak=True)
    assert match_etag('"abc"', '*')
    assert match_etag('w/"abc"', '*')
    assert match_etag('"abc"', '"abc"')

    assert not match_etag('w/"abc"', '"abc"')
    assert not match_etag('"abc"', 'w/"abc"')
    assert not match_etag('"abc"', 'x/"abc"')

    assert match_etag('w/"abc"', '"abc"', weak=True)
    assert match_etag('"abc"', 'w/"abc"', weak=True)
    assert match_etag('"abc"', '"abc", w/"abc"')


def test_match_malformed_etag():
    assert_raises(ValueError, match_etag, 'xxx', '"xxx"')


def test_total_seconds():
    td = timedelta(days=2.5, seconds=.1, microseconds=54)
    assert total_seconds(td) == 216000.100054


def test_cache_control():
    assert_raises(ValueError, cache_control, public=1, private=1)
    assert cache_control(private=True) == 'private'
    assert cache_control(max_age=60, public=True, s_maxage=120,
        must_revalidate=True, proxy_revalidate=True, no_cache=True,
        no_store=True) == 'public, max-age=60, s-maxage=120, no-cache, no-store, must-revalidate, proxy-revalidate'
    assert cache_control(max_age=timedelta(hours=2), s_maxage=timedelta(hours=1)) == 'max-age=7200, s-maxage=3600'
